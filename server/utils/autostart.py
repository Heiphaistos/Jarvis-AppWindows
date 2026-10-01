"""« Démarrer avec la session » pour le panneau web (agent local).

Windows : valeur « JARVIS Web » sous HKCU\\...\\Run (aucun droit administrateur).
Linux : ~/.config/autostart/jarvis-web.desktop (GNOME, KDE, XFCE…).
"""
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

_NAME = "JARVIS Web"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--web", "--no-browser"]
    return [sys.executable, str(Path(__file__).parents[1] / "main.py"), "--web", "--no-browser"]


def _desktop_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "jarvis-web.desktop"


def is_enabled() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.QueryValueEx(key, _NAME)
            return True
        except OSError:
            return False
    return _desktop_file().exists()


def set_enabled(enabled: bool) -> None:
    if sys.platform == "win32":
        import subprocess
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command()))
            else:
                try:
                    winreg.DeleteValue(key, _NAME)
                except FileNotFoundError:
                    pass
        return
    path = _desktop_file()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\nType=Application\nName=JARVIS Web\n"
        "Comment=Assistant JARVIS en arrière-plan (panneau web)\n"
        f"Exec={shlex.join(command())}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )
