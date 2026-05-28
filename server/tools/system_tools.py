from __future__ import annotations
import subprocess
from pathlib import Path
from datetime import datetime
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
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "vlc": "vlc.exe",
}

ALLOWED_KILL_APPS: frozenset[str] = frozenset({
    "chrome.exe", "firefox.exe", "notepad.exe", "calc.exe",
    "code.exe", "wt.exe", "notepad++.exe", "vlc.exe",
    "wmplayer.exe", "mspaint.exe", "wordpad.exe",
    "spotify.exe", "discord.exe",
})


def open_application(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return "Erreur: nom d'application invalide (chaîne non vide requise)."
    key = name.strip().lower()
    if key not in ALLOWED_APPS:
        available = ", ".join(ALLOWED_APPS.keys())
        return f"Application '{name}' non autorisée. Disponibles: {available}"
    exe = ALLOWED_APPS[key]
    try:
        subprocess.Popen([exe], shell=False, creationflags=0x08000000)
        return f"Application '{name}' lancée."
    except FileNotFoundError:
        return f"Erreur: '{exe}' introuvable. L'application est-elle installée ?"
    except Exception as e:
        return f"Erreur lancement '{name}': {e}"


def kill_application(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return "Erreur: nom d'application invalide."
    name = name.strip().lower()
    killed = 0
    for proc in psutil.process_iter(["name"]):
        proc_name = (proc.info.get("name") or "").lower()
        if proc_name not in ALLOWED_KILL_APPS:
            continue
        if name in proc_name:
            try:
                proc.terminate()
                killed += 1
            except Exception:
                pass
    if killed:
        return f"{killed} processus '{name}' terminé(s)."
    return f"Aucun processus autorisé '{name}' trouvé."


def take_screenshot() -> str:
    """Capture the primary screen and save to Desktop."""
    try:
        desktop = Path.home() / "Desktop"
        desktop.mkdir(exist_ok=True)
        filename = f"jarvis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = desktop / filename

        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$s=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            "$b=New-Object System.Drawing.Bitmap $s.Width,$s.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($b);"
            "$g.CopyFromScreen($s.Location,[System.Drawing.Point]::Empty,$s.Size);"
            f"$b.Save('{filepath}');"
            "$g.Dispose();$b.Dispose()"
        )
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=15, creationflags=0x08000000,
        )
        if result.returncode == 0 and filepath.exists():
            size_kb = filepath.stat().st_size // 1024
            return f"Screenshot sauvegardé: {filepath} ({size_kb} KB)"
        return f"Échec screenshot: {result.stderr[:150]}"
    except Exception as e:
        logger.error(f"Erreur screenshot: {e}")
        return f"Erreur screenshot: {e}"


def read_clipboard() -> str:
    """Read current clipboard content."""
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000,
        )
        content = result.stdout.strip()
        if not content:
            return "Presse-papiers vide."
        preview = content[:500] + ("..." if len(content) > 500 else "")
        return f"Presse-papiers ({len(content)} caractères):\n{preview}"
    except Exception as e:
        return f"Erreur lecture presse-papiers: {e}"


def write_clipboard(text: str) -> str:
    """Write text to clipboard via stdin (injection-safe)."""
    if not isinstance(text, str):
        return "Erreur: texte invalide."
    if len(text) > 100_000:
        return "Erreur: texte trop long (max 100 000 caractères)."
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command",
             "$t=[Console]::In.ReadToEnd(); Set-Clipboard -Value $t"],
            input=text, text=True, capture_output=True, timeout=8, creationflags=0x08000000,
        )
        if result.returncode == 0:
            return f"Copié dans le presse-papiers ({len(text)} caractères)."
        return f"Erreur: {result.stderr[:100]}"
    except Exception as e:
        return f"Erreur écriture presse-papiers: {e}"
