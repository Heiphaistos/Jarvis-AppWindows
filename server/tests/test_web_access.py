"""Panneau web local (agent) et version hébergée : session, Host, Origin."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api import security
from api.security import AccessMiddleware, configure
from api.web_routes import router as web_router

PORT = 8765
LOCAL = f"http://127.0.0.1:{PORT}"


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AccessMiddleware)
    app.include_router(web_router, prefix="/api")

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/memories")
    async def memories() -> dict:
        return {"facts": []}

    @app.post("/api/providers")
    async def providers() -> dict:
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        await socket.send_text("ok")
        await socket.close()

    return app


@pytest.fixture(autouse=True)
def _reset_access():
    yield
    configure("desktop", port=PORT)


# ── Bureau (Tauri) ──────────────────────────────────────────────────────────

def test_desktop_mode_keeps_api_open_but_refuses_foreign_writes():
    configure("desktop", port=PORT)
    c = TestClient(_app(), base_url=LOCAL)
    assert c.get("/api/memories").status_code == 200
    assert c.post("/api/providers", headers={"Origin": "http://tauri.localhost"}).status_code == 200
    # Un site ouvert dans le navigateur ne peut pas modifier JARVIS…
    assert c.post("/api/providers", headers={"Origin": "https://evil.example"}).status_code == 403
    # … ni ouvrir le WebSocket (CSWSH).
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers={"Origin": "https://evil.example"}) as s:
            s.receive_text()


# ── Agent local ─────────────────────────────────────────────────────────────

def test_agent_requires_session_and_token_exchange():
    access = configure("agent", port=PORT)
    c = TestClient(_app(), base_url=LOCAL)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/memories").status_code == 401
    assert c.get("/api/session").json() == {"mode": "agent", "authenticated": False, "passwordConfigured": None}

    bad = c.post("/api/session", json={"token": "nope"}, headers={"Origin": LOCAL})
    assert bad.status_code == 403
    ok = c.post("/api/session", json={"token": access.launch_token}, headers={"Origin": LOCAL})
    assert ok.status_code == 200
    cookie = ok.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie

    assert c.get("/api/memories").status_code == 200
    assert c.get("/api/session").json()["authenticated"] is True
    ws_headers = {"Origin": LOCAL, "Host": "127.0.0.1:8765",
                  "Cookie": f"{security.COOKIE}={c.cookies[security.COOKIE]}"}
    with c.websocket_connect("/ws", headers=ws_headers) as s:
        assert s.receive_text() == "ok"
    with pytest.raises(WebSocketDisconnect):  # sans session
        with c.websocket_connect("/ws", headers={"Origin": LOCAL, "Host": "127.0.0.1:8765", "Cookie": ""}) as s:
            s.receive_text()


def test_agent_rejects_dns_rebinding_and_cross_site_writes():
    access = configure("agent", port=PORT)
    c = TestClient(_app(), base_url=LOCAL)
    c.post("/api/session", json={"token": access.launch_token}, headers={"Origin": LOCAL})
    # DNS rebinding : la page d'un attaquant résolue vers 127.0.0.1 garde son Host.
    assert c.get("/api/memories", headers={"Host": "evil.example:8765"}).status_code == 421
    # Même avec la session, une écriture d'une autre origine est refusée.
    assert c.post("/api/providers", headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/providers").status_code == 403  # Origin absente
    assert c.post("/api/providers", headers={"Origin": LOCAL}).status_code == 200


def test_agent_lan_accepts_any_host_but_still_needs_the_key():
    configure("agent", port=PORT, lan=True)
    c = TestClient(_app(), base_url="http://192.168.1.20:8765")
    assert c.get("/api/memories").status_code == 401


def test_session_cookie_is_signed_and_scoped_to_the_mode():
    access = configure("agent", port=PORT)
    value = access.new_session()
    assert access.session_valid(value)
    assert not access.session_valid(value[:-2] + "xx")
    assert not access.session_valid("agent.9999999999.abc.forged")
    other = configure("agent", port=PORT)  # nouveau lancement → nouvelle clé
    assert not other.session_valid(value)


# ── Version hébergée ────────────────────────────────────────────────────────

def test_hosted_login_with_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("api.web_routes.asyncio.sleep", _no_sleep)
    origin = "https://jarvis.example.org"
    configure("hosted", port=PORT, password="s3cret", public_origin=origin, data_dir=tmp_path)
    c = TestClient(_app(), base_url=origin)
    h = {"Origin": origin}
    assert c.get("/api/memories").status_code == 401
    assert c.post("/api/login", json={"password": "bad"}, headers=h).status_code == 401
    ok = c.post("/api/login", json={"password": "s3cret"}, headers=h)
    assert ok.status_code == 200 and "secure" in ok.headers["set-cookie"].lower()
    assert c.get("/api/memories").status_code == 200
    # Clé de signature conservée : une session survit au redémarrage du conteneur.
    assert (tmp_path / "web_secret.key").stat().st_size == 32

    c2 = TestClient(_app(), base_url=origin)
    for _ in range(security.LOGIN_MAX_FAILURES):
        c2.post("/api/login", json={"password": "x"}, headers=h)
    assert c2.post("/api/login", json={"password": "s3cret"}, headers=h).status_code == 429


def test_hosted_rejects_other_hosts():
    origin = "https://jarvis.example.org"
    configure("hosted", port=PORT, password="p", public_origin=origin)
    c = TestClient(_app(), base_url="https://other.example.org")
    assert c.get("/api/health").status_code == 421


def test_hosted_disables_tools_acting_on_the_server():
    from tools.registry import HOST_TOOLS, ToolRegistry
    reg = ToolRegistry()
    assert reg.disable(HOST_TOOLS, "version web hébergée") == len(HOST_TOOLS)
    names = {s["name"] for s in reg.schemas()}
    assert not names & HOST_TOOLS
    assert {"get_weather", "web_search", "set_reminder", "calculate"} <= names
    assert "indisponible" in reg.execute("type_text", text="x")


async def _no_sleep(_s: float) -> None:
    return None


def test_shutdown_requires_the_launch_token(monkeypatch):
    """POST /api/shutdown : seul JARVIS.exe (jeton passé au lancement) peut arrêter le serveur."""
    from api.routes import router
    app = FastAPI()
    app.include_router(router, prefix="/api")
    c = TestClient(app, base_url=LOCAL)
    monkeypatch.delenv("JARVIS_SHUTDOWN_TOKEN", raising=False)
    assert c.post("/api/shutdown", headers={"X-Jarvis-Token": ""}).status_code == 403
    monkeypatch.setenv("JARVIS_SHUTDOWN_TOKEN", "s3cret")
    assert c.post("/api/shutdown").status_code == 403
    assert c.post("/api/shutdown", headers={"X-Jarvis-Token": "wrong"}).status_code == 403
    assert c.post("/api/shutdown", headers={"X-Jarvis-Token": "s3cret"}).status_code == 200


def test_login_limit_is_per_visitor_behind_a_local_proxy():
    """Derrière nginx sans JARVIS_TRUST_PROXY, chaque visiteur garde sa propre limite d'essais."""
    from starlette.requests import Request
    configure("hosted", port=PORT, password="un-mot-de-passe-long")

    def ip(peer: str, fwd: str = "") -> str:
        headers = [(b"x-forwarded-for", fwd.encode())] if fwd else []
        return security.client_ip(Request({"type": "http", "client": (peer, 1234), "headers": headers}))

    assert ip("127.0.0.1", "203.0.113.7") == "203.0.113.7"           # nginx sur la machine
    assert ip("172.18.0.1", "198.51.100.1, 203.0.113.8") == "203.0.113.8"  # réseau Docker : l'entrée de nginx
    assert ip("8.8.8.8", "1.2.3.4") == "8.8.8.8"                                    # client direct : en-tête ignoré
    assert ip("127.0.0.1") == "127.0.0.1"
