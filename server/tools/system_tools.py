from __future__ import annotations
import subprocess
import psutil
from utils.logger import get_logger

logger = get_logger("system_tools")

ALLOWED_APPS: dict[str, str] = {
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "calculator": "calc.exe",
    "vscode": "code.exe",
    "terminal": "wt.exe",
}


def open_application(name: str) -> str:
    key = name.lower().strip()
    if key not in ALLOWED_APPS:
        available = ", ".join(ALLOWED_APPS.keys())
        return f"Application '{name}' non autorisée. Disponibles: {available}"
    exe = ALLOWED_APPS[key]
    subprocess.Popen([exe], shell=True, creationflags=0x08000000)
    return f"Application '{name}' lancée."


def kill_application(name: str) -> str:
    killed = 0
    for proc in psutil.process_iter(["name"]):
        proc_name = proc.info.get("name") or ""
        if name.lower() in proc_name.lower():
            proc.terminate()
            killed += 1
    if killed:
        return f"{killed} processus '{name}' terminés."
    return f"Aucun processus '{name}' trouvé."
