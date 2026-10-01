"""Routes du panneau web : session, connexion, contrôle de l'agent local."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.security import (
    COOKIE, client_ip, get_access, session_info, set_session_cookie,
)
from utils.logger import get_logger

logger = get_logger("web")
router = APIRouter()


class TokenBody(BaseModel):
    token: str = ""


class LoginBody(BaseModel):
    password: str = ""


class AutostartBody(BaseModel):
    enabled: bool


@router.get("/session")
async def get_session(request: Request) -> dict:
    return session_info(request)


@router.post("/session")
async def open_session(body: TokenBody, request: Request) -> JSONResponse:
    """Agent local : échange le jeton du lien (#t=…) contre un cookie de session."""
    access = get_access()
    if access.mode != "agent" or not access.check_token(body.token):
        raise HTTPException(status_code=403, detail="Jeton invalide")
    response = JSONResponse({"ok": True})
    set_session_cookie(response, request)
    return response


@router.post("/login")
async def login(body: LoginBody, request: Request) -> JSONResponse:
    """Version hébergée : connexion par mot de passe, 5 essais par 5 minutes."""
    access = get_access()
    if access.mode != "hosted":
        raise HTTPException(status_code=404, detail="Indisponible")
    ip = client_ip(request)
    if access.login_blocked(ip):
        raise HTTPException(status_code=429, detail="Trop d'essais. Réessayez dans quelques minutes.")
    if not access.check_password(body.password):
        access.login_failed(ip)
        logger.warning(f"Connexion refusée depuis {ip}")
        await asyncio.sleep(0.8)  # ralentit les essais en rafale
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    access.login_succeeded(ip)
    logger.info(f"Connexion depuis {ip}")
    response = JSONResponse({"ok": True})
    set_session_cookie(response, request)
    return response


@router.post("/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE, path="/")
    return response


# ── Agent local ─────────────────────────────────────────────────────────────

def _require_agent() -> None:
    if get_access().mode != "agent":
        raise HTTPException(status_code=404, detail="Indisponible")


@router.post("/agent/shutdown")
async def agent_shutdown() -> dict:
    """Bouton « Arrêter JARVIS » du panneau web."""
    _require_agent()
    from utils.lifecycle import request_shutdown
    logger.info("Arrêt demandé depuis le panneau web")
    # Laisse partir la réponse avant d'arrêter le serveur.
    asyncio.get_running_loop().call_later(0.3, request_shutdown)
    return {"ok": True}


@router.get("/agent/autostart")
async def agent_autostart_status() -> dict:
    _require_agent()
    from utils.autostart import is_enabled
    return {"enabled": await asyncio.to_thread(is_enabled)}


@router.post("/agent/autostart")
async def agent_autostart_set(body: AutostartBody) -> dict:
    _require_agent()
    from utils.autostart import set_enabled
    try:
        await asyncio.to_thread(set_enabled, body.enabled)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Impossible : {e}")
    return {"enabled": body.enabled}
