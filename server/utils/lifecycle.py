"""Arrêt propre du serveur depuis l'API (bouton « Arrêter » du panneau web)."""
from __future__ import annotations

from typing import Callable

_shutdown: Callable[[], None] | None = None


def set_shutdown_handler(handler: Callable[[], None]) -> None:
    global _shutdown
    _shutdown = handler


def request_shutdown() -> bool:
    if _shutdown is None:
        return False
    _shutdown()
    return True
