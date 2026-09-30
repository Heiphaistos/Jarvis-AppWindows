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
from core.monitor import run_monitor as _run_monitor
from tools.registry import ToolRegistry
from api.routes import router
from api.websocket import websocket_handler

logger = get_logger("main")

# Lancé via `python main.py`, ce module s'appelle "__main__" — sans cet alias,
# tout `import main` (routes API) RÉIMPORTERAIT le module : doubles instances
# LLM (VRAM ×2 !) et profils appliqués à des objets fantômes.
sys.modules.setdefault("main", sys.modules[__name__])

# Profils de performance : le persisté est la CIBLE, mais le premier chargement
# se fait TOUJOURS en Économie (safe boot) — protège le matériel si une erreur
# de config rendait le profil demandé trop gourmand.
from utils.perf import (
    load_profile as _load_perf, active_profile as _active_perf,
    set_profile as _set_perf, downgrade_of as _downgrade_of,
    PROFILES as _PERF_PROFILES, VRAM_CEILING_PCT,
)
_target_perf = _load_perf()
_safe_boot = _PERF_PROFILES["eco"]
settings.n_gpu_layers = _safe_boot.n_gpu_layers
settings.n_ctx = _safe_boot.n_ctx
settings.whisper_compute_type = _safe_boot.whisper_compute

llm = LLMManager(settings)
stt = STTManager(settings)
tts = TTSManager(settings)
tools = ToolRegistry()

# Init persistent memory early so tools can access the singleton
from core.persistent_memory import get_memory as _init_memory
_init_memory()

# Provider manager — cerveau LLM interchangeable (local par défaut)
from core.providers import init_provider_manager
from core.persistent_memory import _DB_PATH as _MEM_DB_PATH
providers = init_provider_manager(llm, _MEM_DB_PATH.parent)
# La voix Gemini réutilise la clé du cerveau Gemini (onglet CERVEAU).
tts.set_key_provider(lambda: providers.api_key("gemini"))


def _vram_pct() -> float | None:
    """% de VRAM utilisée (GPU le plus chargé), None sans GPU NVIDIA."""
    import subprocess
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, creationflags=0x08000000,
        )
        if proc.returncode != 0:
            return None
        parts = proc.stdout.strip().split("\n")[0].split(",")
        return float(parts[0]) / float(parts[1]) * 100
    except Exception:
        return None


async def _load_models_background() -> None:
    """Safe boot : charge en Économie, puis monte vers le profil cible si la
    VRAM le permet. Uvicorn reste accessible pendant ce temps."""
    logger.info("Chargement du modèle LLM en mode Économie (safe boot)...")
    await asyncio.to_thread(llm.load)
    logger.info("Chargement STT Whisper...")
    await asyncio.to_thread(stt.load)
    if providers.tier == "local":
        from core.prompt import build_system_prompt
        await llm.warmup(build_system_prompt("local", "", stable=True))
    logger.info(f"JARVIS prêt (éco) — LLM: {llm.is_available} | STT: {stt.is_available} | TTS: {tts.is_available}")
    from core.monitor import broadcast_direct as _broadcast_direct
    _broadcast_direct("server_status", {
        "llm": providers.is_available,
        "stt": stt.is_available,
        "tts": tts.is_available,
        "provider": providers.active.name,
        "providerLabel": providers.active.label,
        "providerModel": providers.active.model,
    })
    # Montée vers le profil cible persisté, avec vérification VRAM + rollback
    if _target_perf.name != "eco" and llm.is_available:
        logger.info(f"Safe boot OK — montée vers le profil {_target_perf.label}...")
        _set_perf(_target_perf.name)
        await apply_performance_profile()


_reload_lock = asyncio.Lock()


async def _reload_with(profile) -> None:
    settings.n_gpu_layers = profile.n_gpu_layers
    settings.n_ctx = profile.n_ctx
    settings.whisper_compute_type = profile.whisper_compute
    llm.unload()
    stt.unload()
    await asyncio.to_thread(llm.load)
    await asyncio.to_thread(stt.load)
    if providers.tier == "local" and llm.is_available:
        from core.prompt import build_system_prompt
        await llm.warmup(build_system_prompt("local", "", stable=True))


async def apply_performance_profile() -> None:
    """Recharge LLM + STT avec le profil actif, puis PROTOCOLE MATÉRIEL :
    si la VRAM dépasse le plafond de 80 %, rollback automatique d'un cran."""
    async with _reload_lock:
        profile = _active_perf()
        logger.info(f"Rechargement des modèles — profil {profile.label}...")
        await _reload_with(profile)

        # Garde-fou post-chargement : jamais au-dessus de VRAM_CEILING_PCT
        message = f"Profil {profile.label} appliqué — modèles rechargés."
        vram = await asyncio.to_thread(_vram_pct)
        while vram is not None and vram > VRAM_CEILING_PCT:
            lower = _downgrade_of(profile.name)
            if lower is None:
                logger.warning(f"VRAM {vram:.0f}% > {VRAM_CEILING_PCT}% même en éco")
                message = f"⚠️ VRAM à {vram:.0f}% même en Économie — fermez des applications GPU."
                break
            logger.warning(
                f"PROTOCOLE MATÉRIEL: VRAM {vram:.0f}% > {VRAM_CEILING_PCT}% "
                f"— rollback {profile.label} → {lower}"
            )
            profile = _set_perf(lower)
            await _reload_with(profile)
            vram = await asyncio.to_thread(_vram_pct)
            message = (
                f"⚠️ Protocole matériel : VRAM au-dessus de {VRAM_CEILING_PCT:.0f}% — "
                f"profil rétrogradé en {profile.label} (VRAM {vram:.0f}%)."
                if vram is not None else
                f"⚠️ Profil rétrogradé en {profile.label} (protection matériel)."
            )

        from core.monitor import broadcast_direct as _bd
        _bd("server_status", {
            "llm": providers.is_available,
            "stt": stt.is_available,
            "tts": tts.is_available,
            "provider": providers.active.name,
            "providerLabel": providers.active.label,
            "providerModel": providers.active.model,
        })
        _bd("notice", {"message": message})
        _bd("perf_changed", {"active": profile.name})
        logger.info(f"Profil {profile.label} actif (VRAM {vram if vram is not None else '—'}%)")


# ── Gardien runtime : surveille la VRAM en continu (protection matériel) ─────
_guard_cooldown_until = 0.0


async def _vram_guardian(vram_pct: float) -> None:
    """Appelé par le monitor quand la VRAM dépasse le plafond de façon
    soutenue → rétrograde d'un cran automatiquement."""
    global _guard_cooldown_until
    import time as _time
    if _time.monotonic() < _guard_cooldown_until or _reload_lock.locked():
        return
    current = _active_perf()
    lower = _downgrade_of(current.name)
    if lower is None:
        return  # déjà en éco — rien à rétrograder
    _guard_cooldown_until = _time.monotonic() + 180  # 3 min entre interventions
    logger.warning(
        f"PROTOCOLE MATÉRIEL: VRAM {vram_pct:.0f}% soutenue > {VRAM_CEILING_PCT}% "
        f"— rétrogradation {current.label} → {lower}"
    )
    from core.monitor import broadcast_direct as _bd
    _bd("notice", {"message": (
        f"⚠️ Protocole matériel : VRAM à {vram_pct:.0f}% — "
        f"rétrogradation automatique du profil {current.label}."
    )})
    _set_perf(lower)
    await apply_performance_profile()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Démarrage JARVIS Core...")
    # Protection matériel : le monitor surveille la VRAM et rétrograde le
    # profil automatiquement si elle dépasse le plafond de façon soutenue.
    from core.monitor import set_vram_guardian
    set_vram_guardian(_vram_guardian)
    # Lancer le chargement en background pour que le port s'ouvre immédiatement
    model_task = asyncio.create_task(_load_models_background())
    monitor_task = asyncio.create_task(_run_monitor())
    yield  # ← port 8765 ouvert ici, modèles chargent en arrière-plan
    model_task.cancel()
    monitor_task.cancel()
    for task in (model_task, monitor_task):
        try:
            await task
        except asyncio.CancelledError:
            pass
    llm.unload()
    logger.info("JARVIS arrêté.")


app = FastAPI(title="JARVIS Core", version="4.7.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await websocket_handler(
        ws, providers, stt, tts, tools,
        max_context_messages=settings.max_context_messages,
    )


if __name__ == "__main__":
    import uvicorn
    # PyInstaller sans console → sys.stdout/stderr sont None, ce qui fait planter
    # uvicorn.logging.DefaultFormatter via isatty(). On redirige vers devnull.
    if getattr(sys, "frozen", False):
        import io
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_config=None,  # évite la config logging d'uvicorn qui appelle isatty()
        ws_ping_interval=20,
        ws_ping_timeout=30,
    )
