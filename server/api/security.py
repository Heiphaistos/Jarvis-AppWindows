"""Accès à JARVIS depuis un navigateur : panneau web local et version hébergée.

Trois modes (``settings.mode``) :

- ``desktop`` : l'application Tauri. Pas de session ; seules les origines de
  l'application (et du serveur Vite en développement) peuvent écrire ou ouvrir
  le WebSocket — un site ouvert dans le navigateur ne peut pas piloter JARVIS.
- ``agent`` : panneau web local, comme NiTriTe Agent. Chaque lancement tire un
  jeton de 256 bits, transmis à l'onglet dans le fragment de l'URL (``#t=…``,
  jamais envoyé sur le réseau), puis échangé contre un cookie de session
  HttpOnly. L'en-tête Host est vérifié (parade au DNS rebinding).
- ``hosted`` : version web sur un VPS. Connexion par mot de passe
  (``JARVIS_PASSWORD``), tentatives limitées, cookie Secure derrière HTTPS.

Dans les deux modes web, toute l'API et le WebSocket exigent la session, et
toute écriture doit venir de la page elle-même (Origin = l'hôte servi).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from utils.logger import get_logger

logger = get_logger("security")

COOKIE = "jarvis_session"
MIN_PASSWORD_CHARS = 12  # version hébergée
DESKTOP_ORIGINS = frozenset({
    "http://localhost:1420",    # dev Vite
    "http://127.0.0.1:1420",
    "tauri://localhost",         # Tauri (macOS / Linux)
    "http://tauri.localhost",    # Tauri v2 (WebView2, Windows)
    "https://tauri.localhost",
})
# Accessibles sans session (l'interface elle-même, et de quoi ouvrir une session).
PUBLIC_API = frozenset({"/api/health", "/api/session", "/api/login", "/api/logout"})
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_S = 300.0
SESSION_TTL_S = {"agent": 7 * 86400, "hosted": 30 * 86400}


@dataclass
class Access:
    mode: str = "desktop"
    launch_token: str = ""
    password: str = ""
    public_origin: str = ""
    allowed_hosts: frozenset[str] | None = None  # None : tout Host accepté (--lan)
    trust_proxy: bool = False
    secret: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    _failures: dict[str, deque] = field(default_factory=lambda: defaultdict(deque))

    @property
    def web(self) -> bool:
        return self.mode in ("agent", "hosted")

    # ── Sessions : cookie signé, sans état côté serveur ────────────────────

    def new_session(self) -> str:
        expiry = int(time.time()) + SESSION_TTL_S.get(self.mode, 86400)
        payload = f"{self.mode}.{expiry}.{secrets.token_urlsafe(9)}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).digest()
        return f"{payload}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"

    def session_valid(self, value: str | None) -> bool:
        if not value or value.count(".") != 3:
            return False
        payload, _, sig = value.rpartition(".")
        expected = base64.urlsafe_b64encode(
            hmac.new(self.secret, payload.encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        if not hmac.compare_digest(sig, expected):
            return False
        mode, expiry, _ = payload.split(".", 2)
        return mode == self.mode and expiry.isdigit() and int(expiry) > time.time()

    def check_token(self, token: str) -> bool:
        return bool(self.launch_token) and hmac.compare_digest(
            str(token).encode(), self.launch_token.encode()
        )

    def check_password(self, password: str) -> bool:
        if not self.password:
            return False
        a = hashlib.sha256(str(password).encode()).digest()
        b = hashlib.sha256(self.password.encode()).digest()
        return hmac.compare_digest(a, b)

    # ── Limitation des tentatives de connexion ─────────────────────────────

    def login_blocked(self, client: str) -> bool:
        q = self._failures[client]
        now = time.monotonic()
        while q and now - q[0] > LOGIN_WINDOW_S:
            q.popleft()
        return len(q) >= LOGIN_MAX_FAILURES

    def login_failed(self, client: str) -> None:
        self._failures[client].append(time.monotonic())

    def login_succeeded(self, client: str) -> None:
        self._failures.pop(client, None)

    # ── Host / Origin ──────────────────────────────────────────────────────

    def host_allowed(self, host: str) -> bool:
        if not self.web or self.allowed_hosts is None:
            return True
        return host.lower() in self.allowed_hosts

    def origin_allowed(self, origin: str, host: str, scheme: str) -> bool:
        """Une écriture ou un WebSocket ne peut venir que de la page servie."""
        if not self.web:
            return origin in DESKTOP_ORIGINS
        if self.public_origin:
            return origin.rstrip("/") == self.public_origin.rstrip("/")
        return origin == f"{scheme}://{host}" or (
            # https:// devant un proxy qui ne transmet pas X-Forwarded-Proto
            self.mode == "hosted" and origin == f"https://{host}"
        )


_access = Access()


def get_access() -> Access:
    return _access


def configure(
    mode: str,
    *,
    port: int,
    lan: bool = False,
    password: str = "",
    public_origin: str = "",
    trust_proxy: bool = False,
    data_dir: Path | None = None,
) -> Access:
    """Prépare l'accès pour le mode choisi. Retourne l'objet (jeton compris)."""
    global _access
    mode = mode if mode in ("desktop", "agent", "hosted") else "desktop"
    access = Access(mode=mode, password=password, public_origin=public_origin.rstrip("/"),
                    trust_proxy=trust_proxy)
    if mode == "agent":
        access.launch_token = secrets.token_urlsafe(32)
        if not lan:
            access.allowed_hosts = frozenset({f"127.0.0.1:{port}", f"localhost:{port}"})
    elif mode == "hosted":
        if public_origin:
            access.allowed_hosts = frozenset({urlsplit(public_origin).netloc.lower()})
        # Clé de signature persistante : une mise à jour du conteneur ne
        # déconnecte pas.
        if data_dir is not None:
            access.secret = _load_secret(data_dir / "web_secret.key")
    _access = access
    return access


def _load_secret(path: Path) -> bytes:
    try:
        data = path.read_bytes()
        if len(data) >= 32:
            return data
    except OSError:
        pass
    data = secrets.token_bytes(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
    except OSError as e:
        logger.warning(f"Clé de session non persistée ({e}) : reconnexion après redémarrage.")
    return data


# ── Middleware ASGI (HTTP et WebSocket) ─────────────────────────────────────

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; media-src 'self' data: blob:; font-src 'self' data:; "
    "worker-src 'self' blob:; connect-src 'self' {ws}; frame-ancestors 'none'; "
    "base-uri 'none'; form-action 'self'; object-src 'none'"
)


def _scheme(headers: Headers, scope: dict, access: Access) -> str:
    if access.trust_proxy:
        proto = headers.get("x-forwarded-proto", "").split(",")[0].strip()
        if proto in ("http", "https"):
            return proto
    return "https" if scope.get("scheme") in ("https", "wss") else "http"


def _behind_local_proxy(peer: str) -> bool:
    """Pair local ou privé (nginx sur la machine, réseau Docker) : un visiteur d'Internet
    ne peut pas arriver de là, la requête a donc traversé notre propre proxy."""
    try:
        ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def client_ip(request: Request) -> str:
    access = get_access()
    peer = request.client.host if request.client else "?"
    fwd = request.headers.get("x-forwarded-for", "")
    # Sans cela, derrière un nginx oublié en JARVIS_TRUST_PROXY=0, tous les visiteurs
    # auraient l'IP du proxy : 5 erreurs de l'un bloqueraient la connexion de tous.
    if fwd and (access.trust_proxy or _behind_local_proxy(peer)):
        return fwd.split(",")[-1].strip()  # ajouté par NOTRE proxy (le dernier)
    return peer


class AccessMiddleware:
    """Session, Host et Origin pour toute l'API et le WebSocket ; en-têtes de sécurité."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        access = get_access()
        headers = Headers(scope=scope)
        host = headers.get("host", "")
        path = scope.get("path", "")
        is_ws = scope["type"] == "websocket"
        method = scope.get("method", "GET")
        scheme = _scheme(headers, scope, access)

        if not access.host_allowed(host):
            logger.warning(f"Host refusé: {host!r}")
            return await self._deny(scope, receive, send, 421, "Host non autorisé")

        origin = headers.get("origin")
        writes = is_ws or method not in ("GET", "HEAD", "OPTIONS")
        if origin and writes and not access.origin_allowed(origin, host, scheme):
            # En desktop, les requêtes sans Origin (outils locaux) restent permises.
            logger.warning(f"Origine refusée: {origin!r} sur {path}")
            return await self._deny(scope, receive, send, 403, "Origine non autorisée")
        if access.web and writes and not origin:
            return await self._deny(scope, receive, send, 403, "Origine manquante")

        guarded = path == "/ws" or (path.startswith("/api/") and path not in PUBLIC_API)
        if access.web and guarded:
            cookie = _cookie(headers.get("cookie", ""), COOKIE)
            if not access.session_valid(cookie):
                return await self._deny(scope, receive, send, 401, "Session requise")

        if is_ws or not access.web:
            return await self.app(scope, receive, send)

        ws_src = f"{'wss' if scheme == 'https' else 'ws'}://{host}"

        async def _send(message) -> None:
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                h.setdefault("X-Content-Type-Options", "nosniff")
                h.setdefault("Referrer-Policy", "no-referrer")
                h.setdefault("X-Frame-Options", "DENY")
                h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
                h.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
                if h.get("content-type", "").startswith("text/html"):
                    h.setdefault("Content-Security-Policy", _CSP.format(ws=ws_src))
                    h.setdefault("Cache-Control", "no-cache")
                if scheme == "https":
                    h.setdefault("Strict-Transport-Security", "max-age=31536000")
            await send(message)

        return await self.app(scope, receive, _send)

    @staticmethod
    async def _deny(scope, receive, send, status: int, detail: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4000 + status, "reason": detail})
            return
        await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)


def _cookie(raw: str, name: str) -> str | None:
    for part in raw.split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return None


def set_session_cookie(response: Response, request: Request) -> None:
    access = get_access()
    scheme = _scheme(request.headers, request.scope, access)
    response.set_cookie(
        COOKIE, access.new_session(),
        max_age=SESSION_TTL_S.get(access.mode) if access.mode == "hosted" else None,
        httponly=True, samesite="lax", secure=scheme == "https", path="/",
    )


def session_info(request: Request) -> dict:
    access = get_access()
    return {
        "mode": access.mode,
        "authenticated": (not access.web) or access.session_valid(request.cookies.get(COOKIE)),
        "passwordConfigured": bool(access.password) if access.mode == "hosted" else None,
    }
