"""Emplacements des données (mémoire, réglages, jetons) et des journaux.

- ``JARVIS_DATA_DIR`` / ``JARVIS_LOG_DIR`` l'emportent (Docker, VPS).
- Windows, exécutable compilé : à côté de l'exe (comportement historique,
  les mémoires existantes restent en place).
- Linux, exécutable compilé : l'exe est en lecture seule (AppImage, /usr/bin),
  donc ~/.local/share/JARVIS (XDG).
- Développement : server/data et .logs à la racine du dépôt.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_FROZEN = bool(getattr(sys, "frozen", False))


def _xdg_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "JARVIS"


def data_dir() -> Path:
    env = os.environ.get("JARVIS_DATA_DIR")
    if env:
        return Path(env)
    if _FROZEN:
        if sys.platform == "win32":
            return Path(sys.executable).parent / "data"
        return _xdg_home() / "data"
    return Path(__file__).parents[1] / "data"


def logs_dir() -> Path:
    env = os.environ.get("JARVIS_LOG_DIR")
    if env:
        return Path(env)
    if _FROZEN:
        if sys.platform == "win32":
            return Path(sys.executable).parent / ".logs"
        return _xdg_home() / "logs"
    return Path(__file__).parents[2] / ".logs"
