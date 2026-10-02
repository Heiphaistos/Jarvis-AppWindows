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


def _fix_stdio() -> None:
    # PyInstaller sans console → sys.stdout/stderr sont None : uvicorn (isatty)
    # et argparse (--help) planteraient en écrivant dedans.
    if getattr(sys, "frozen", False):
        import io
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()


def _parse_cli():
    """Options de lancement, appliquées AVANT la lecture des réglages."""
    import argparse
    p = argparse.ArgumentParser(prog="jarvis_server", description="Serveur J.A.R.V.I.S.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--web", action="store_true",
                      help="panneau web local : l'interface s'ouvre dans le navigateur, sans fenêtre native")
    mode.add_argument("--hosted", action="store_true",
                      help="version web hébergée (VPS) : mot de passe, cerveaux cloud, sans accès au PC")
    p.add_argument("--port", type=int, help="port d'écoute (défaut 8765)")
    p.add_argument("--host", help="adresse d'écoute (défaut 127.0.0.1)")
    p.add_argument("--lan", action="store_true",
                   help="panneau web accessible depuis le réseau local (le lien contient la clé)")
    p.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    p.add_argument("--app", action="store_true",
                   help="ouvrir le panneau dans une fenêtre d'application Edge/Chrome (sans onglets)")
    args, _unknown = p.parse_known_args()
    if args.web:
        os.environ["JARVIS_MODE"] = "agent"
    elif args.hosted:
        os.environ["JARVIS_MODE"] = "hosted"
    if args.port:
        os.environ["JARVIS_PORT"] = str(args.port)
    if args.lan:
        os.environ["JARVIS_HOST"] = "0.0.0.0"
    if args.host:
        os.environ["JARVIS_HOST"] = args.host
    return args


_cli = None
if __name__ == "__main__":
    _fix_stdio()
    _cli = _parse_cli()

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
from api.web_routes import router as web_router
from api.websocket import websocket_handler
from api.security import AccessMiddleware, configure as _configure_access

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
from api.websocket import voice_available as _voice_available
from core.persistent_memory import get_memory as _init_memory
_init_memory()

# Provider manager — cerveau LLM interchangeable (local par défaut)
from core.providers import init_provider_manager
from core.persistent_memory import _DB_PATH as _MEM_DB_PATH
from core.reminders import init_reminders
reminders = init_reminders(_MEM_DB_PATH.parent / "reminders.json")
providers = init_provider_manager(llm, _MEM_DB_PATH.parent)
# La voix Gemini réutilise la clé du cerveau Gemini (onglet CERVEAU).
tts.set_key_provider(lambda: providers.api_key("gemini"))


def _vram_pct() -> float | None:
    """% de VRAM utilisée (GPU le plus chargé), None sans GPU NVIDIA."""
    import subprocess
    from utils.platform import NO_WINDOW
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, creationflags=NO_WINDOW,
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
    if settings.local_models:
        logger.info("Chargement du modèle LLM en mode Économie (safe boot)...")
        await asyncio.to_thread(llm.load)
        logger.info("Chargement STT Whisper...")
        await asyncio.to_thread(stt.load)
    else:
        logger.info("Modèles locaux désactivés (JARVIS_LOCAL_MODELS=0) : cerveaux et voix cloud.")
    if providers.tier == "local":
        from core.prompt import build_system_prompt
        await llm.warmup(build_system_prompt("local", "", stable=True))
    logger.info(f"JARVIS prêt (éco) — LLM: {llm.is_available} | STT: {stt.is_available} | TTS: {tts.is_available}")
    from core.monitor import broadcast_direct as _broadcast_direct
    _broadcast_direct("server_status", {
        "llm": providers.is_available,
        "stt": _voice_available(stt, providers),
        "tts": tts.is_available,
        "provider": providers.active.name,
        "providerLabel": providers.active.label,
        "providerModel": providers.active.model,
    })
    # Montée vers le profil cible persisté, avec vérification VRAM + rollback
    if _target_perf.name != "eco" and llm.is_available and settings.local_models:
        logger.info(f"Safe boot OK — montée vers le profil {_target_perf.label}...")
        _set_perf(_target_perf.name)
        await apply_performance_profile()


_reload_lock = asyncio.Lock()


async def _reload_with(profile) -> None:
    settings.n_gpu_layers = profile.n_gpu_layers
    settings.n_ctx = profile.n_ctx
    settings.whisper_compute_type = profile.whisper_compute
    if not settings.local_models:
        return  # aucun modèle local à recharger (version web hébergée)
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
            "stt": _voice_available(stt, providers),
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
    logger.info(f"Démarrage JARVIS Core (mode {settings.mode})...")
    # Protection matériel : le monitor surveille la VRAM et rétrograde le
    # profil automatiquement si elle dépasse le plafond de façon soutenue.
    from core.monitor import set_vram_guardian
    set_vram_guardian(_vram_guardian)
    # Lancer le chargement en background pour que le port s'ouvre immédiatement
    model_task = asyncio.create_task(_load_models_background())
    monitor_task = asyncio.create_task(_run_monitor())
    # Minuteurs et rappels : annoncés à tous les clients connectés à l'échéance.
    from core.monitor import broadcast_direct as _bd_rem

    async def _reminder_due(r) -> None:
        if r.kind == "routine":
            # Routine : briefing condensé, contrôle PC (muet si tout va bien), message.
            from core.routines import run as _run_routine
            message = await _run_routine(r, providers)
            if message:
                _bd_rem("reminder", {"id": r.id, "kind": "routine", "message": message})
            return
        _bd_rem("reminder", {"id": r.id, "kind": r.kind, "message": r.message})

    reminder_task = asyncio.create_task(reminders.run(_reminder_due))

    async def _keep_brains_warm() -> None:
        # Connexions TLS gardées ouvertes vers les cerveaux cloud (1er mot plus rapide).
        while True:
            if providers.tier == "cloud":
                try:
                    await providers.warmup()
                except Exception as e:
                    logger.debug(f"Préchauffage des cerveaux: {e}")
            await asyncio.sleep(90)

    warm_task = asyncio.create_task(_keep_brains_warm())
    yield  # ← port 8765 ouvert ici, modèles chargent en arrière-plan
    model_task.cancel()
    monitor_task.cancel()
    reminder_task.cancel()
    warm_task.cancel()
    for task in (model_task, monitor_task, reminder_task, warm_task):
        try:
            await task
        except asyncio.CancelledError:
            pass
    llm.unload()
    logger.info("JARVIS arrêté.")


app = FastAPI(title="JARVIS Core", version="5.5.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost",
                   "http://tauri.localhost", "https://tauri.localhost"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
# Ajouté après CORS → exécuté avant : session, Host et Origin d'abord.
app.add_middleware(AccessMiddleware)
app.include_router(router, prefix="/api")
app.include_router(web_router, prefix="/api")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await websocket_handler(
        ws, providers, stt, tts, tools,
        max_context_messages=settings.max_context_messages,
    )


def setup_web(app: FastAPI) -> None:
    """Modes panneau web / hébergé : accès, outils, interface servie par le serveur."""
    from utils.paths import data_dir
    access = _configure_access(
        settings.mode, port=settings.port, lan=settings.host not in ("127.0.0.1", "localhost"),
        password=settings.password, public_origin=settings.public_origin,
        trust_proxy=settings.trust_proxy, data_dir=data_dir(),
    )
    if not access.web:
        return
    if settings.mode == "hosted":
        from tools.registry import HOST_TOOLS
        tools.disable(HOST_TOOLS, "version web hébergée — JARVIS n'a pas accès au PC de Monsieur.")
        if not settings.password:
            logger.error("JARVIS_PASSWORD manquant : personne ne pourra se connecter.")
    index = settings.web_dir / "index.html"
    if index.is_file():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=settings.web_dir, html=True), name="web")
        logger.info(f"Interface web servie depuis {settings.web_dir}")
    else:
        logger.error(f"Interface web introuvable ({index}) : lancez « npm run build » dans client/.")


def _agent_session_file():
    from utils.paths import data_dir
    return data_dir() / "web-agent.json"


def _reuse_running_agent(open_browser: bool, app_window: bool) -> bool:
    """Un panneau web tourne déjà : rouvrir son onglet au lieu d'en lancer un second."""
    import json as _json
    import urllib.request
    try:
        info = _json.loads(_agent_session_file().read_text(encoding="utf-8"))
        url = f"http://127.0.0.1:{int(info['port'])}"
        with urllib.request.urlopen(f"{url}/api/session", timeout=2) as r:
            if _json.loads(r.read()).get("mode") != "agent":
                return False
    except Exception:
        return False
    if open_browser:
        from utils.browser import open_panel
        open_panel(f"{url}/#t={info['token']}", app_window)
    return True


def _free_port(host: str, port: int) -> int:
    """Le port demandé, sinon le suivant libre (l'application de bureau occupe peut-être 8765)."""
    import socket
    for candidate in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host if host != "localhost" else "127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    return port


def _write_agent_session(token: str) -> None:
    import json as _json
    path = _agent_session_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps({"port": settings.port, "token": token, "pid": os.getpid()}),
                    encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


if __name__ == "__main__":
    import uvicorn
    from utils.lifecycle import set_shutdown_handler

    open_browser = settings.mode == "agent" and not (_cli and _cli.no_browser)
    app_window = bool(_cli and _cli.app)
    if settings.mode == "agent":
        if _reuse_running_agent(open_browser, app_window):
            sys.exit(0)
        settings.port = _free_port(settings.host, settings.port)

    setup_web(app)
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_config=None,  # évite la config logging d'uvicorn qui appelle isatty()
        ws_ping_interval=20,
        ws_ping_timeout=30,
        proxy_headers=settings.trust_proxy,
        forwarded_allow_ips="*" if settings.trust_proxy else None,
    )
    server = uvicorn.Server(config)

    def _shutdown() -> None:
        server.should_exit = True

    set_shutdown_handler(_shutdown)

    if settings.mode == "agent":
        from api.security import get_access
        token = get_access().launch_token
        _write_agent_session(token)
        url = f"http://127.0.0.1:{settings.port}/#t={token}"
        logger.info(f"Panneau web : http://127.0.0.1:{settings.port} (lien avec clé ouvert dans le navigateur)")
        print(f"JARVIS — panneau web : {url}", flush=True)
        if open_browser:
            import threading
            from utils.browser import open_when_ready
            threading.Thread(target=open_when_ready, args=(settings.port, url, app_window),
                             daemon=True).start()
    try:
        server.run()
    finally:
        if settings.mode == "agent":
            try:
                _agent_session_file().unlink(missing_ok=True)
            except OSError:
                pass
