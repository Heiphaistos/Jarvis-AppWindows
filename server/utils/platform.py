"""Différences Windows / Linux regroupées ici : le reste du serveur ne teste
plus ``sys.platform`` lui-même."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# CREATE_NO_WINDOW : pas de console qui clignote sous Windows. Ailleurs,
# subprocess refuse toute valeur non nulle de creationflags.
NO_WINDOW = 0x08000000 if IS_WINDOWS else 0

EXE_SUFFIX = ".exe" if IS_WINDOWS else ""


def which_first(*candidates: str) -> str | None:
    """Premier programme présent dans le PATH parmi ``candidates``."""
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


def run(args: list[str], timeout: float = 10, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run sans fenêtre console, sortie texte capturée."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    return subprocess.run(args, timeout=timeout, creationflags=NO_WINDOW, **kwargs)


def spawn_detached(args: list[str]) -> subprocess.Popen:
    """Lance une application sans la rattacher à JARVIS (elle survit à son arrêt)."""
    if IS_WINDOWS:
        return subprocess.Popen(args, shell=False, creationflags=NO_WINDOW)
    return subprocess.Popen(
        args, shell=False, start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def desktop_dir() -> Path:
    """Dossier Bureau de l'utilisateur (XDG_DESKTOP_DIR sous Linux : « Bureau » en français)."""
    if IS_LINUX:
        try:
            out = run(["xdg-user-dir", "DESKTOP"], timeout=3).stdout.strip()
            if out and Path(out).is_dir() and Path(out) != Path.home():
                return Path(out)
        except Exception:
            pass
        for name in ("Bureau", "Desktop"):
            if (Path.home() / name).is_dir():
                return Path.home() / name
    return Path.home() / "Desktop"


def is_wayland() -> bool:
    return IS_LINUX and bool(os.environ.get("WAYLAND_DISPLAY"))
