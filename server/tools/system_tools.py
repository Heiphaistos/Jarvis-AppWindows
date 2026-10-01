from __future__ import annotations
from tools.decorator import tool
from pathlib import Path
from datetime import datetime
import psutil
from utils.logger import get_logger
from utils.platform import IS_WINDOWS, desktop_dir, is_wayland, run, spawn_detached, which_first

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

# Linux : mêmes noms d'applications, premier programme installé de la liste.
LINUX_APPS: dict[str, tuple[str, ...]] = {
    "chrome": ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave-browser"),
    "firefox": ("firefox", "firefox-esr"),
    "notepad": ("gnome-text-editor", "gedit", "kate", "kwrite", "mousepad", "xed", "pluma"),
    "explorer": ("nautilus", "dolphin", "thunar", "nemo", "pcmanfm", "caja"),
    "calculator": ("gnome-calculator", "kcalc", "galculator", "mate-calc", "qalculate-gtk"),
    "vscode": ("code", "codium"),
    "terminal": ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"),
    "spotify": ("spotify",),
    "discord": ("discord", "Discord"),
    "vlc": ("vlc",),
}

ALLOWED_KILL_APPS: frozenset[str] = frozenset({
    "chrome.exe", "firefox.exe", "notepad.exe", "calc.exe",
    "code.exe", "wt.exe", "notepad++.exe", "vlc.exe",
    "wmplayer.exe", "mspaint.exe", "wordpad.exe",
    "spotify.exe", "discord.exe",
    # Linux (noms de processus, sans extension)
    "chrome", "chromium", "chromium-browser", "firefox", "firefox-esr", "gnome-text-editor",
    "gedit", "kate", "kwrite", "mousepad", "gnome-calculator", "kcalc", "galculator",
    "code", "codium", "vlc", "spotify", "discord",
})


@tool
def open_application(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return "Erreur: nom d'application invalide (chaîne non vide requise)."
    key = name.strip().lower()
    if key not in ALLOWED_APPS:
        available = ", ".join(ALLOWED_APPS.keys())
        return f"Application '{name}' non autorisée. Disponibles: {available}"
    if IS_WINDOWS:
        exe = ALLOWED_APPS[key]
    else:
        exe = which_first(*LINUX_APPS[key])
        if exe is None:
            return f"Erreur: aucune application « {name} » installée ({', '.join(LINUX_APPS[key][:3])}…)."
    try:
        spawn_detached([exe])
        return f"Application '{name}' lancée."
    except FileNotFoundError:
        return f"Erreur: '{exe}' introuvable. L'application est-elle installée ?"
    except Exception as e:
        return f"Erreur lancement '{name}': {e}"


@tool
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


def _linux_screenshot(filepath: Path) -> str | None:
    """Capture d'écran sous Linux avec l'outil installé ; None si réussie, sinon l'erreur."""
    candidates: list[list[str]] = []
    if is_wayland():
        candidates += [["grim", str(filepath)], ["gnome-screenshot", "-f", str(filepath)],
                       ["spectacle", "-b", "-n", "-f", "-o", str(filepath)]]
    candidates += [["gnome-screenshot", "-f", str(filepath)], ["spectacle", "-b", "-n", "-f", "-o", str(filepath)],
                   ["scrot", "-o", str(filepath)], ["maim", str(filepath)],
                   ["import", "-window", "root", str(filepath)]]
    for cmd in candidates:
        if which_first(cmd[0]) is None:
            continue
        try:
            r = run(cmd, timeout=15)
            if r.returncode == 0 and filepath.exists():
                return None
        except Exception:
            continue
    try:
        from PIL import ImageGrab  # type: ignore[import]
        ImageGrab.grab().save(filepath)
        return None
    except Exception as e:
        return f"aucun outil de capture (installez gnome-screenshot, grim ou scrot) — {e}"


@tool
def take_screenshot() -> str:
    """Capture the primary screen and save to Desktop."""
    try:
        desktop = desktop_dir()
        desktop.mkdir(exist_ok=True)
        filename = f"jarvis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = desktop / filename
        if not IS_WINDOWS:
            error = _linux_screenshot(filepath)
            if error:
                return f"Échec screenshot: {error}"
            return f"Screenshot sauvegardé: {filepath} ({filepath.stat().st_size // 1024} KB)"

        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$s=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            "$b=New-Object System.Drawing.Bitmap $s.Width,$s.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($b);"
            "$g.CopyFromScreen($s.Location,[System.Drawing.Point]::Empty,$s.Size);"
            f"$b.Save('{filepath}');"
            "$g.Dispose();$b.Dispose()"
        )
        result = run(["powershell", "-NonInteractive", "-Command", ps_script], timeout=15)
        if result.returncode == 0 and filepath.exists():
            size_kb = filepath.stat().st_size // 1024
            return f"Screenshot sauvegardé: {filepath} ({size_kb} KB)"
        return f"Échec screenshot: {result.stderr[:150]}"
    except Exception as e:
        logger.error(f"Erreur screenshot: {e}")
        return f"Erreur screenshot: {e}"


def _linux_clipboard(read: bool) -> list[str] | None:
    """Commande de lecture/écriture du presse-papiers selon la session (Wayland ou X11)."""
    if is_wayland() and which_first("wl-paste"):
        return ["wl-paste", "--no-newline"] if read else ["wl-copy"]
    if which_first("xclip"):
        return ["xclip", "-selection", "clipboard", "-o" if read else "-i"]
    if which_first("xsel"):
        return ["xsel", "--clipboard", "--output" if read else "--input"]
    return None


@tool
def read_clipboard() -> str:
    """Read current clipboard content."""
    try:
        if IS_WINDOWS:
            cmd = ["powershell", "-NonInteractive", "-Command", "Get-Clipboard"]
        else:
            cmd = _linux_clipboard(read=True)
            if cmd is None:
                return "Presse-papiers inaccessible : installez wl-clipboard (Wayland) ou xclip (X11)."
        result = run(cmd, timeout=5)
        content = result.stdout.strip()
        if not content:
            return "Presse-papiers vide."
        preview = content[:500] + ("..." if len(content) > 500 else "")
        return f"Presse-papiers ({len(content)} caractères):\n{preview}"
    except Exception as e:
        return f"Erreur lecture presse-papiers: {e}"


@tool
def write_clipboard(text: str) -> str:
    """Write text to clipboard via stdin (injection-safe)."""
    if not isinstance(text, str):
        return "Erreur: texte invalide."
    if len(text) > 100_000:
        return "Erreur: texte trop long (max 100 000 caractères)."
    try:
        if IS_WINDOWS:
            cmd = ["powershell", "-NonInteractive", "-Command",
                   "$t=[Console]::In.ReadToEnd(); Set-Clipboard -Value $t"]
        else:
            cmd = _linux_clipboard(read=False)
            if cmd is None:
                return "Presse-papiers inaccessible : installez wl-clipboard (Wayland) ou xclip (X11)."
        result = run(cmd, timeout=8, input=text)
        if result.returncode == 0:
            return f"Copié dans le presse-papiers ({len(text)} caractères)."
        return f"Erreur: {result.stderr[:100]}"
    except Exception as e:
        return f"Erreur écriture presse-papiers: {e}"
