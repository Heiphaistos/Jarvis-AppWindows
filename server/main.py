from __future__ import annotations
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Inject CUDA 12 DLL paths so llama-cpp-python can find cublas64_12.dll
def _add_cuda_dll_dirs() -> None:
    if sys.platform != "win32":
        return
    try:
        import importlib.util, pathlib
        for _pkg in ("nvidia.cublas", "nvidia.cuda_runtime"):
            spec = importlib.util.find_spec(_pkg.replace(".", "."))
            if spec and spec.submodule_search_locations:
                for _loc in spec.submodule_search_locations:
                    _bin = pathlib.Path(_loc) / "bin"
                    if _bin.exists():
                        os.add_dll_directory(str(_bin))
    except Exception:
        pass

_add_cuda_dll_dirs()

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from utils.logger import get_logger
from utils.config import settings
from core.llm import LLMManager
from core.stt import STTManager
from core.tts import TTSManager
from tools.registry import ToolRegistry
from api.routes import router
from api.websocket import websocket_handler

logger = get_logger("main")

llm = LLMManager(settings)
stt = STTManager(settings)
tts = TTSManager(settings)
tools = ToolRegistry()

# Init persistent memory early so tools can access the singleton
from core.persistent_memory import get_memory as _init_memory
_init_memory()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Démarrage JARVIS Core...")
    logger.info("Chargement du modèle LLM (peut prendre 30-60s)...")
    await asyncio.to_thread(llm.load)
    logger.info("Chargement STT Whisper...")
    await asyncio.to_thread(stt.load)
    logger.info(f"JARVIS prêt — LLM: {llm.is_available} | STT: {stt.is_available} | TTS: {tts.is_available}")
    yield
    llm.unload()
    logger.info("JARVIS arrêté.")


app = FastAPI(title="JARVIS Core", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await websocket_handler(
        ws, llm, stt, tts, tools,
        max_context_messages=settings.max_context_messages,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        ws_ping_interval=20,
        ws_ping_timeout=30,
    )
