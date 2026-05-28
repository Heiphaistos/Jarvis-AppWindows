from __future__ import annotations
import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
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
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="2.0.0")


@router.get("/memories/count")
async def memories_count() -> dict:
    try:
        from core.persistent_memory import get_memory
        return {"count": get_memory().count()}
    except Exception:
        return {"count": 0}


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

# ── Gmail OAuth ─────────────────────────────────────────────────────────────

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
    _DATA_DIR.mkdir(exist_ok=True)
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

def _build_gmail_auth_url() -> str:
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]
    flow = InstalledAppFlow.from_client_secrets_file(
        str(_CREDS_FILE),
        scopes=GMAIL_SCOPES,
        redirect_uri="http://localhost:8765/api/auth/gmail/callback",
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
        redirect_uri="http://localhost:8765/api/auth/gmail/callback",
    )
    flow.fetch_token(code=code)
    _DATA_DIR.mkdir(exist_ok=True)
    _TOKEN_FILE.write_text(flow.credentials.to_json())
    logger.info("Token Gmail sauvegardé")
