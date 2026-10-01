from __future__ import annotations
import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from utils.config import MODELS_DIR
from tools.info_tools import get_system_info
from tools.email_tools import (
    _DATA_DIR, _CREDS_FILE, _TOKEN_FILE, GMAIL_SCOPES, gmail_status,
)
from utils.logger import get_logger

logger = get_logger("routes")
router = APIRouter()

_PIPER_DIR = MODELS_DIR / "piper"

# ── Models ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str

class VoicesResponse(BaseModel):
    voices: list[str]

class SystemInfoResponse(BaseModel):
    info: str

class GmailStatusResponse(BaseModel):
    status: str          # "non_configured" | "not_authenticated" | "connected"
    auth_url: str | None = None

# ── Basic endpoints ─────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", version=request.app.version)


@router.get("/memories/count")
async def memories_count() -> dict:
    try:
        from core.persistent_memory import get_memory
        return {"count": get_memory().count()}
    except Exception:
        return {"count": 0}


class AutoMemoryRequest(BaseModel):
    enabled: bool


@router.get("/memories")
async def memories_list() -> dict:
    """Tout ce que JARVIS sait sur Monsieur + leçons apprises + état de la mémoire auto."""
    from core.auto_memory import is_enabled
    from core.persistent_memory import get_memory
    memory = get_memory()
    return {
        "facts": memory.facts(), "lessons": memory.lessons(),
        "episodes": memory.episodes(limit=20), "auto": is_enabled(),
    }


@router.delete("/memories/{key}")
async def memories_forget(key: str) -> dict:
    from core.persistent_memory import get_memory
    if not get_memory().forget(key):
        raise HTTPException(status_code=404, detail="Souvenir introuvable")
    return {"ok": True}


@router.delete("/lessons/{lesson_id}")
async def lessons_forget(lesson_id: int) -> dict:
    from core.persistent_memory import get_memory
    if not get_memory().forget_lesson(lesson_id):
        raise HTTPException(status_code=404, detail="Leçon introuvable")
    return {"ok": True}


@router.delete("/episodes/{episode_id}")
async def episodes_forget(episode_id: int) -> dict:
    from core.persistent_memory import get_memory
    if not get_memory().forget_episode(episode_id):
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return {"ok": True}


@router.post("/memories/auto")
async def memories_auto(req: AutoMemoryRequest) -> dict:
    from core.auto_memory import is_enabled, set_enabled
    set_enabled(req.enabled)
    return {"auto": is_enabled()}


@router.get("/voices", response_model=VoicesResponse)
async def list_voices() -> VoicesResponse:
    voices: list[str] = []
    if _PIPER_DIR.exists():
        for f in _PIPER_DIR.glob("*.onnx"):
            if "tashkeel" not in f.name:
                voices.append(f.stem)
    return VoicesResponse(voices=sorted(voices))


@router.get("/system_info", response_model=SystemInfoResponse)
async def system_info() -> SystemInfoResponse:
    info = await asyncio.to_thread(get_system_info)
    return SystemInfoResponse(info=info)

# ── Performance ─────────────────────────────────────────────────────────────

class PerfRequest(BaseModel):
    profile: str


@router.get("/performance")
async def performance_status() -> dict:
    from utils.perf import status as perf_status
    return perf_status()


@router.post("/performance")
async def performance_set(req: PerfRequest) -> dict:
    """Change le profil et recharge les modèles en arrière-plan (~30-60 s)."""
    from utils.perf import set_profile, status as perf_status
    if set_profile(req.profile) is None:
        raise HTTPException(status_code=400, detail=f"Profil inconnu: {req.profile}")
    import main  # lazy — évite l'import circulaire, main est déjà chargé
    asyncio.create_task(main.apply_performance_profile())
    return {**perf_status(), "reloading": True}


# ── Providers LLM ───────────────────────────────────────────────────────────

class ProviderConfigRequest(BaseModel):
    name: str
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    activate: bool = False
    # Mode AUTO : chaînes de cerveaux par niveau (instant/standard/deep) et course au 1er token
    chains: dict[str, list[str]] | None = None
    hedging: bool | None = None


@router.get("/providers")
async def providers_status() -> dict:
    """Liste des providers + provider actif. Les clés API sont masquées."""
    from core.providers import get_provider_manager
    return get_provider_manager().status()


@router.post("/providers")
async def providers_configure(req: ProviderConfigRequest) -> dict:
    """Configure et/ou active un provider LLM. Localhost uniquement (bind 127.0.0.1)."""
    from core.providers import get_provider_manager
    pm = get_provider_manager()
    if req.chains is not None or req.hedging is not None:
        error = pm.set_routing(req.chains, req.hedging)
        if error:
            raise HTTPException(status_code=400, detail=error)
    if req.name not in ("local", "auto") and any(
        v is not None for v in (req.api_key, req.model, req.base_url)
    ):
        error = pm.configure(req.name, {
            "api_key": req.api_key, "model": req.model, "base_url": req.base_url,
        })
        if error:
            raise HTTPException(status_code=400, detail=error)
    if req.activate:
        error = pm.set_active(req.name)
        if error:
            raise HTTPException(status_code=400, detail=error)
    return pm.status()

class CustomProviderRequest(BaseModel):
    label: str
    base_url: str
    model: str = ""
    api_key: str = ""
    kind: str = "openai"


@router.post("/providers/custom")
async def providers_add_custom(req: CustomProviderRequest) -> dict:
    """Ajoute une API (compatible OpenAI ou Anthropic) depuis l'onglet Cerveau."""
    from core.providers import get_provider_manager
    pm = get_provider_manager()
    name, error = pm.add_custom(req.label, req.base_url, req.model, req.api_key, req.kind)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {**pm.status(), "created": name}


@router.delete("/providers/custom/{name}")
async def providers_remove_custom(name: str) -> dict:
    from core.providers import get_provider_manager
    pm = get_provider_manager()
    error = pm.remove_custom(name)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return pm.status()


@router.get("/providers/{name}/models")
async def providers_models(name: str) -> dict:
    """Modèles proposés par un fournisseur, avec la clé enregistrée côté serveur."""
    import httpx
    from core.providers import get_provider_manager
    from core.providers.discovery import list_models
    try:
        return {"models": await list_models(get_provider_manager(), name)}
    except (ValueError, httpx.HTTPError) as e:
        raise HTTPException(status_code=400, detail=str(e) or "Fournisseur injoignable")


@router.post("/providers/{name}/test")
async def providers_test(name: str) -> dict:
    """Teste la connexion à un fournisseur (clé, adresse, modèle)."""
    from core.providers import get_provider_manager
    from core.providers.discovery import test_connection
    try:
        return await test_connection(get_provider_manager(), name)
    except ValueError as e:
        return {"ok": False, "detail": str(e)}


# ── Réglages (Paramètres › Voix, Moteurs) ───────────────────────────────────

class SettingsUpdate(BaseModel):
    values: dict[str, bool | int | float | str]


@router.get("/settings")
async def settings_get() -> dict:
    from utils.runtime_settings import get_settings
    rs = get_settings()
    return {"values": rs.snapshot(), "schema": rs.schema()}


@router.post("/settings")
async def settings_update(req: SettingsUpdate) -> dict:
    from utils.runtime_settings import SettingsError, get_settings
    rs = get_settings()
    try:
        values = rs.update(req.values)
    except SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"values": values, "schema": rs.schema()}


# ── Gmail OAuth ─────────────────────────────────────────────────────────────

# ── Comptes connectés ───────────────────────────────────────────────────────

class ConnectionUpdate(BaseModel):
    values: dict[str, str | None] = {}
    allow_write: bool | None = None


@router.get("/connections")
async def connections_status() -> dict:
    """Comptes connectables et leur état. Les secrets ne sont jamais renvoyés."""
    from core.connections import get_store
    return {"connections": get_store().status()}


@router.post("/connections/{cid}")
async def connections_update(cid: str, req: ConnectionUpdate) -> dict:
    from core.connections import get_store
    try:
        get_store().update(cid, req.values, req.allow_write)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"connections": get_store().status()}


@router.post("/connections/{cid}/test")
async def connections_test(cid: str) -> dict:
    import tools.connection_tools  # noqa: F401 — enregistre les fonctions de test
    from core.connections import get_store, test_connection
    result = await asyncio.to_thread(test_connection, cid)
    return {**result, "connections": get_store().status()}


@router.delete("/connections/{cid}")
async def connections_remove(cid: str) -> dict:
    from core.connections import CONNECTORS, get_store
    if cid not in CONNECTORS:
        raise HTTPException(status_code=404, detail="Compte inconnu")
    get_store().remove(cid)
    return {"connections": get_store().status()}


@router.get("/auth/gmail/status", response_model=GmailStatusResponse)
async def gmail_auth_status() -> GmailStatusResponse:
    status = gmail_status()
    if status == "not_authenticated":
        auth_url = await asyncio.to_thread(_build_gmail_auth_url)
        return GmailStatusResponse(status=status, auth_url=auth_url)
    return GmailStatusResponse(status=status)


@router.post("/auth/gmail/upload_credentials")
async def upload_gmail_credentials(file: UploadFile = File(...)) -> dict:
    """Accept google_credentials.json uploaded from the settings panel."""
    content = await file.read()
    try:
        creds = json.loads(content)
        # Validate structure
        entry = creds.get("installed") or creds.get("web")
        if not entry or "client_id" not in entry:
            raise ValueError("Format invalide")
    except Exception:
        raise HTTPException(status_code=400, detail="Fichier credentials.json invalide.")
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _CREDS_FILE.write_bytes(content)
    auth_url = await asyncio.to_thread(_build_gmail_auth_url)
    return {"status": "credentials_saved", "auth_url": auth_url}


@router.get("/auth/gmail/start")
async def gmail_auth_start() -> dict:
    """Return the OAuth2 URL the user should open in their browser."""
    if not _CREDS_FILE.exists():
        raise HTTPException(status_code=400, detail="google_credentials.json manquant.")
    auth_url = await asyncio.to_thread(_build_gmail_auth_url)
    return {"auth_url": auth_url}


@router.get("/auth/gmail/callback")
async def gmail_auth_callback(code: str = "", error: str = "") -> HTMLResponse:
    """Google redirects here after user grants access."""
    if error or not code:
        return HTMLResponse("<html><body><h2>Authentification annulée.</h2></body></html>")
    try:
        await asyncio.to_thread(_exchange_code_for_token, code)
        return HTMLResponse(
            "<html><body style='font-family:monospace;background:#010d1a;color:#00d4ff;padding:40px'>"
            "<h2>✓ Gmail connecté avec succès.</h2>"
            "<p>Vous pouvez fermer cet onglet et revenir à J.A.R.V.I.S.</p>"
            "</body></html>"
        )
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return HTMLResponse(f"<html><body><h2>Erreur: {e}</h2></body></html>")


@router.delete("/auth/gmail/disconnect")
async def gmail_disconnect() -> dict:
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.unlink()
    return {"status": "disconnected"}


# ── OAuth helpers (sync, run in thread) ─────────────────────────────────────

def _gmail_redirect_uri() -> str:
    """Adresse de retour OAuth : l'adresse publique en version hébergée, sinon localhost."""
    from utils.config import settings
    base = settings.public_origin.rstrip("/") or f"http://localhost:{settings.port}"
    return f"{base}/api/auth/gmail/callback"


def _build_gmail_auth_url() -> str:
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]
    flow = InstalledAppFlow.from_client_secrets_file(
        str(_CREDS_FILE),
        scopes=GMAIL_SCOPES,
        redirect_uri=_gmail_redirect_uri(),
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def _exchange_code_for_token(code: str) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]
    flow = InstalledAppFlow.from_client_secrets_file(
        str(_CREDS_FILE),
        scopes=GMAIL_SCOPES,
        redirect_uri=_gmail_redirect_uri(),
    )
    flow.fetch_token(code=code)
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(flow.credentials.to_json())
    logger.info("Token Gmail sauvegardé")
