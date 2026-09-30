from __future__ import annotations

import asyncio

import httpx

# Un client HTTP partagé par boucle asyncio : les connexions TLS vers les
# cerveaux cloud restent ouvertes d'un message à l'autre (keep-alive), au lieu
# d'une nouvelle poignée de main (≈ 100-300 ms) à chaque requête.
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
_LIMITS = httpx.Limits(max_connections=40, max_keepalive_connections=20, keepalive_expiry=120.0)
_clients: dict[int, httpx.AsyncClient] = {}


def shared_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    key = id(loop)
    client = _clients.get(key)
    if client is None or client.is_closed:
        # Nettoie les clients des boucles fermées (tests, redémarrages)
        for k in [k for k, c in _clients.items() if c.is_closed]:
            _clients.pop(k, None)
        client = httpx.AsyncClient(timeout=_TIMEOUT, limits=_LIMITS)
        _clients[key] = client
    return client


async def warm(url: str, headers: dict[str, str] | None = None) -> float | None:
    """Ouvre (ou garde ouverte) la connexion vers `url` ; retourne la durée en s, None si échec."""
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        await shared_client().get(url, headers=headers or {}, timeout=5.0)
        return loop.time() - t0
    except httpx.HTTPError:
        return None
