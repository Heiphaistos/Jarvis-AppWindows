from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("nitrite")

# Pont vers NiTriTe Agent (panneau web de NiTriTe) : l'agent tourne sur le PC,
# écoute sur 127.0.0.1 et expose les commandes de diagnostic de NiTriTe.
# Il écrit son port et son jeton dans %LOCALAPPDATA%\NiTriTe-WebPanel\session.json ;
# JARVIS les lit et appelle POST /api/invoke/<commande> avec l'en-tête
# x-nitrite-token — même sécurité que le navigateur, rien n'est affaibli.
#
# Seules des commandes EN LECTURE SEULE sont autorisées : pas d'effacement de
# disque, de désinstallation ni de réglage système depuis la voix.
READ_ONLY_COMMANDS = {
    "get_system_info", "get_battery_detailed", "get_battery_extended", "get_disks_smart",
    "get_storage_physical_info", "get_temperatures", "get_cpu_core_temps", "get_gpu_temps",
    "get_ram_detailed", "get_gpu_detailed", "get_bsod_history", "get_event_logs",
    "get_startup_programs", "check_system_health", "get_perf_snapshot",
    "get_top_processes_by_cpu",
}

_TIMEOUT = 60  # certaines commandes WMI/PowerShell prennent plusieurs secondes


class NitriteUnavailable(RuntimeError):
    pass


def _session_path() -> Path | None:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "NiTriTe-WebPanel" / "session.json" if base else None


def session() -> dict | None:
    """Session de l'agent en cours (port, jeton), ou None s'il ne tourne pas."""
    override = os.environ.get("JARVIS_NITRITE_SESSION")
    path = Path(override) if override else _session_path()
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        port, token = int(data["port"]), str(data["token"])
    except (ValueError, KeyError, TypeError, OSError):
        return None
    return {"port": port, "token": token}


def _request(method: str, path: str, sess: dict, body: dict | None = None, timeout: float = _TIMEOUT):
    url = f"http://127.0.0.1:{sess['port']}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "x-nitrite-token": sess["token"], "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None


def is_running() -> bool:
    sess = session()
    if sess is None:
        return False
    try:
        _request("GET", "/api/health", sess, timeout=2)
        return True
    except Exception:
        return False


def invoke(command: str, args: dict | None = None):
    """Appelle une commande NiTriTe en lecture seule et renvoie son résultat JSON."""
    if command not in READ_ONLY_COMMANDS:
        raise PermissionError(f"Commande NiTriTe non autorisée depuis JARVIS : {command}")
    sess = session()
    if sess is None:
        raise NitriteUnavailable("NiTriTe Agent n'est pas lancé")
    try:
        return _request("POST", f"/api/invoke/{command}", sess, args or {})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        if e.code == 401:
            raise NitriteUnavailable("jeton NiTriTe refusé — relancez NiTriTe Agent") from e
        raise RuntimeError(f"{command} : {detail or e.reason}") from e
    except urllib.error.URLError as e:
        raise NitriteUnavailable("NiTriTe Agent ne répond pas") from e


# ── Lancement de l'agent ─────────────────────────────────────────────────────

def find_agent_exe() -> Path | None:
    """NiTriTe-Agent*.exe : JARVIS_NITRITE_AGENT, sinon emplacements habituels."""
    override = os.environ.get("JARVIS_NITRITE_AGENT")
    if override:
        p = Path(override)
        return p if p.is_file() else None
    home = Path.home()
    dirs = [home / "Downloads", home / "Téléchargements", home / "Desktop", home / "Bureau",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "NiTriTe",
            Path(os.environ.get("LOCALAPPDATA", str(home))) / "NiTriTe-WebPanel"]
    found: list[Path] = []
    for d in dirs:
        if d.is_dir():
            found += [p for p in d.glob("NiTriTe-Agent*.exe") if p.is_file()]
    # La version la plus récente (nom trié) si plusieurs téléchargements.
    return sorted(found, key=lambda p: p.name)[-1] if found else None


def start_agent(wait_s: float = 20.0) -> str:
    """Lance NiTriTe Agent sans navigateur (Windows demande les droits admin)."""
    if is_running():
        return "NiTriTe Agent tourne déjà."
    if sys.platform != "win32":
        return "NiTriTe Agent ne fonctionne que sous Windows."
    exe = find_agent_exe()
    if exe is None:
        return ("NiTriTe-Agent.exe introuvable. Téléchargez-le depuis les releases du dépôt "
                "Nitrite-We-Panel, ou indiquez son chemin dans JARVIS_NITRITE_AGENT.")
    # ShellExecute : déclenche la demande d'élévation UAC voulue par l'agent.
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{exe}' -ArgumentList '--no-browser','--idle-minutes','30'"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        time.sleep(1)
        if is_running():
            return "NiTriTe Agent démarré."
    return "NiTriTe Agent lancé — validez la demande d'administrateur Windows si elle s'affiche."
