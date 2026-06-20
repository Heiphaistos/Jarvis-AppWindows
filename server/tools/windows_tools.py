from __future__ import annotations
import subprocess
import json
import re
import urllib.request
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("windows_tools")

_PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


def _run_ps(command: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(_PS + [command], capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return "Délai dépassé."
    except Exception as e:
        return f"Erreur PowerShell: {e}"


def get_battery() -> str:
    """Retourne le niveau de batterie et l'état de charge."""
    out = _run_ps(
        "(Get-WmiObject -Class Win32_Battery | Select-Object -First 1 | "
        "Select-Object EstimatedChargeRemaining, BatteryStatus) | ConvertTo-Json"
    )
    if not out or out in ("null", ""):
        return "Aucune batterie détectée (appareil de bureau ou batterie non reconnue)."
    try:
        data = json.loads(out)
        pct = data.get("EstimatedChargeRemaining", "?")
        status_code = data.get("BatteryStatus", 0)
        status_map = {
            1: "décharge", 2: "AC branché", 3: "chargement complet",
            4: "faible", 5: "critique", 6: "en charge", 7: "en charge + haute",
            8: "en charge + faible", 9: "en charge + critique", 11: "partiellement chargée",
        }
        status_str = status_map.get(status_code, "inconnu")
        return f"Batterie: {pct}% — {status_str}"
    except Exception:
        return out or "Information batterie indisponible."


def set_volume(level: int) -> str:
    """Règle le volume système entre 0 et 100."""
    level = max(0, min(100, int(level)))
    # Utilise nircmd si disponible, sinon PowerShell WScript
    import shutil
    nircmd = shutil.which("nircmd")
    if nircmd:
        subprocess.run([nircmd, "setsysvolume", str(int(level * 655.35))], capture_output=True)
        return f"Volume réglé à {level}%."
    # Fallback: touches virtuelles (approximatif)
    _run_ps(
        f"$wsh = New-Object -ComObject WScript.Shell; "
        f"for ($i=0;$i -lt 50;$i++) {{ $wsh.SendKeys([char]174) }}; "
        f"for ($i=0;$i -lt [math]::Round({level}/2);$i++) {{ $wsh.SendKeys([char]175) }}"
    )
    return f"Volume réglé à {level}% (approximatif)."


def ping_host(host: str) -> str:
    """Ping un hôte et retourne la latence moyenne."""
    if not re.match(r'^[a-zA-Z0-9.\-_]+$', host) or len(host) > 253:
        return "Hôte invalide."
    # L'hôte est passé via une variable PS affectée en premier (pas d'interpolation directe)
    # même si la regex valide déjà le format — défense en profondeur.
    safe_host = host.replace("'", "")  # double protection : supprime toute apostrophe résiduelle
    out = _run_ps(
        f"$h = '{safe_host}'; "
        f"$r = Test-Connection -ComputerName $h -Count 3 -ErrorAction SilentlyContinue; "
        f"if ($r) {{ "
        f"$avg = ($r | Measure-Object ResponseTime -Average).Average; "
        f"\"Ping $h: $([math]::Round($avg))ms (3 paquets)\" "
        f"}} else {{ \"Hôte $h inaccessible.\" }}"
    )
    return out or f"Ping {host}: pas de réponse."


def get_public_ip() -> str:
    """Retourne l'adresse IP publique."""
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "JARVIS/3.0"})
        ip = urllib.request.urlopen(req, timeout=5).read().decode().strip()
        return f"Adresse IP publique: {ip}"
    except Exception as e:
        return f"Impossible de récupérer l'IP publique: {e}"


def list_directory(path: str = "") -> str:
    """Liste le contenu d'un répertoire (home par défaut)."""
    base = Path.home()
    if path:
        target = (base / path).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return f"Accès refusé: {path} est hors du répertoire home."
    else:
        target = base

    if not target.exists():
        return f"Répertoire introuvable: {target}"
    if not target.is_dir():
        return f"{target} n'est pas un répertoire."

    try:
        items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        dirs = [p for p in items if p.is_dir()]
        files = [p for p in items if p.is_file()]
        lines = [f"📁 {target}"]
        for d in dirs[:20]:
            lines.append(f"  📁 {d.name}/")
        for f in files[:30]:
            size = f.stat().st_size
            size_str = f"{size/1024:.1f} KB" if size > 1024 else f"{size} B"
            lines.append(f"  📄 {f.name} ({size_str})")
        total = len(dirs) + len(files)
        if total > 50:
            lines.append(f"  ... ({total - 50} éléments supplémentaires)")
        return "\n".join(lines)
    except PermissionError:
        return f"Permission refusée: {target}"


def _validate_path(raw_path: str, allowed_roots: list[Path]) -> Path:
    """Résout et valide un chemin contre une liste de racines autorisées."""
    p = Path(raw_path).resolve()  # résout les symlinks et les chemin relatifs
    for root in allowed_roots:
        try:
            p.relative_to(root.resolve())
            return p
        except ValueError:
            continue
    raise PermissionError(f"Accès refusé: {raw_path}")


def read_file(path: str) -> str:
    """Lit le contenu d'un fichier texte (max 5000 caractères)."""
    MAX_CHARS = 5000
    base = Path.home()
    p = Path(path)
    raw = str(p) if p.is_absolute() else str(base / path)

    allowed_roots = [base, Path("C:/Users"), Path("C:/tmp")]
    try:
        target = _validate_path(raw, allowed_roots)
    except PermissionError as e:
        return str(e)

    if not target.exists():
        return f"Fichier introuvable: {target}"
    if not target.is_file():
        return f"{target} n'est pas un fichier."

    size = target.stat().st_size
    if size > 1_000_000:
        return f"Fichier trop volumineux ({size/1024/1024:.1f} MB). Maximum: 1 MB."

    allowed_ext = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
                   ".toml", ".ini", ".cfg", ".log", ".csv", ".html", ".css", ".rs",
                   ".bat", ".ps1", ".sh", ".xml", ".sql"}
    if target.suffix.lower() not in allowed_ext:
        return f"Extension non supportée: {target.suffix}. Formats texte uniquement."

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > MAX_CHARS:
            return content[:MAX_CHARS] + f"\n\n[... tronqué à {MAX_CHARS} caractères sur {len(content)} total]"
        return content
    except Exception as e:
        return f"Erreur lecture: {e}"
