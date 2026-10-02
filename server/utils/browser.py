"""Ouverture du panneau web dans le navigateur déjà installé."""
from __future__ import annotations

import os
import time
import urllib.request
import webbrowser
from pathlib import Path

from utils.logger import get_logger
from utils.platform import IS_WINDOWS, spawn_detached, which_first

logger = get_logger("browser")


def _app_browser() -> str | None:
    """Edge ou Chrome, capables d'ouvrir une fenêtre d'application (--app)."""
    if IS_WINDOWS:
        roots = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        for root in filter(None, roots):
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                exe = Path(root) / rel
                if exe.is_file():
                    return str(exe)
        return None
    return which_first("microsoft-edge", "google-chrome", "google-chrome-stable",
                       "chromium", "chromium-browser", "brave-browser")


def open_panel(url: str, app_window: bool = False) -> None:
    if app_window:
        exe = _app_browser()
        if exe:
            try:
                spawn_detached([exe, f"--app={url}"])
                return
            except OSError as e:
                logger.warning(f"Fenêtre d'application impossible ({e}) : onglet classique.")
    if not webbrowser.open(url):
        logger.warning("Aucun navigateur trouvé : ouvrez le lien affiché dans la console.")


def open_when_ready(port: int, url: str, app_window: bool = False, timeout: float = 30.0) -> None:
    """Attend que le serveur réponde, puis ouvre le panneau (thread de fond)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1):
                break
        except Exception:
            time.sleep(0.25)
    open_panel(url, app_window)
