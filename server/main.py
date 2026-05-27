from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket
from utils.logger import get_logger
from utils.config import settings
from core.llm import LLMManager
from core.memory import ContextMemory
from core.stt import STTManager
from core.tts import TTSManager
from tools.registry import ToolRegistry
from api.routes import router
from api.websocket import websocket_handler

logger = get_logger("main")

llm = LLMManager(settings)
memory = ContextMemory(settings.max_context_messages)
stt = STTManager(settings)
tts = TTSManager(settings)
tools = ToolRegistry()


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
app.include_router(router, prefix="/api")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await websocket_handler(ws, llm, memory, stt, tts, tools)


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
