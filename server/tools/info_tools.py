from __future__ import annotations
import subprocess
import urllib.parse
import urllib.request
import json
import psutil
from utils.logger import get_logger

logger = get_logger("info_tools")

# WMO weather condition codes
_WMO: dict[int, str] = {
    0: "Ciel dégagé ☀️", 1: "Principalement dégagé 🌤️", 2: "Partiellement nuageux ⛅",
    3: "Couvert ☁️", 45: "Brouillard 🌫️", 48: "Brouillard givrant 🌫️",
    51: "Bruine légère 🌦️", 53: "Bruine 🌦️", 55: "Bruine dense 🌧️",
    61: "Pluie légère 🌧️", 63: "Pluie modérée 🌧️", 65: "Pluie forte 🌧️",
    71: "Neige légère 🌨️", 73: "Neige 🌨️", 75: "Neige forte ❄️",
    77: "Grésil ❄️", 80: "Averses légères 🌦️", 81: "Averses 🌧️",
    82: "Averses violentes ⛈️", 85: "Averses de neige 🌨️", 86: "Averses neige fortes ❄️",
    95: "Orage ⛈️", 96: "Orage avec grêle ⛈️", 99: "Orage fort avec grêle ⛈️",
}


def _main_disk_usage() -> str:
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            label = part.mountpoint.rstrip("/\\") or part.device
            return f"Disque {label}: {usage.used // 1024**3}/{usage.total // 1024**3} GB ({usage.percent}%)"
        except (PermissionError, OSError):
            continue
    return "Disque: N/A"


def get_system_info() -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk_str = _main_disk_usage()

    gpu_info = "N/A"
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 5:
                gpu_info = f"{parts[0]} | VRAM: {parts[1]}/{parts[2]} MB | Load: {parts[3]}% | Temp: {parts[4]}°C"
    except Exception:
        pass

    return (
        f"CPU: {cpu}% | "
        f"RAM: {mem.used // 1024**2}/{mem.total // 1024**2} MB ({mem.percent}%) | "
        f"{disk_str} | GPU: {gpu_info}"
    )


def diagnose_system() -> str:
    """Comprehensive Windows system diagnostics."""
    lines: list[str] = ["=== Diagnostic JARVIS ==="]

    # CPU
    try:
        freq = psutil.cpu_freq()
        freq_str = f" @ {freq.current:.0f} MHz" if freq else ""
        lines.append(
            f"CPU: {psutil.cpu_count(logical=False)} cœurs ({psutil.cpu_count()} logiques){freq_str} — {psutil.cpu_percent(interval=0.5)}%"
        )
    except Exception:
        lines.append("CPU: N/A")

    # RAM + swap
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        lines.append(
            f"RAM: {mem.used//1024**3}/{mem.total//1024**3} GB ({mem.percent}%) | "
            f"Swap: {swap.used//1024**3}/{swap.total//1024**3} GB"
        )
    except Exception:
        lines.append("RAM: N/A")

    # Disques
    disk_lines: list[str] = []
    for part in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(part.mountpoint)
            warn = " ⚠️ ESPACE FAIBLE" if u.percent > 85 else ""
            disk_lines.append(f"  {part.mountpoint}: {u.used//1024**3}/{u.total//1024**3} GB ({u.percent}%){warn}")
        except (PermissionError, OSError):
            pass
    if disk_lines:
        lines.append("Stockage:\n" + "\n".join(disk_lines))

    # Réseau
    try:
        net = psutil.net_io_counters()
        lines.append(f"Réseau: ↓ {net.bytes_recv//1024**2} MB reçus | ↑ {net.bytes_sent//1024**2} MB envoyés")
    except Exception:
        pass

    # GPU
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    pwr = f" | Puissance: {parts[5]}W" if len(parts) >= 6 else ""
                    lines.append(
                        f"GPU {parts[0]}: VRAM {parts[1]}/{parts[2]} MB | Load {parts[3]}% | Temp {parts[4]}°C{pwr}"
                    )
    except Exception:
        pass

    # Top 5 processus RAM
    try:
        procs = sorted(
            psutil.process_iter(["name", "cpu_percent", "memory_info", "pid"]),
            key=lambda p: (p.info.get("memory_info") or type("", (), {"rss": 0})()).rss,
            reverse=True,
        )[:5]
        proc_lines = []
        for p in procs:
            try:
                rss = (p.info["memory_info"].rss // 1024**2) if p.info.get("memory_info") else 0
                cpu = p.info.get("cpu_percent") or 0
                proc_lines.append(f"  [{p.info['pid']}] {p.info.get('name','?')}: RAM {rss}MB | CPU {cpu:.1f}%")
            except Exception:
                pass
        if proc_lines:
            lines.append("Top processus (RAM):\n" + "\n".join(proc_lines))
    except Exception:
        pass

    # Dernières erreurs Windows Event Log
    try:
        r = subprocess.run(
            ["powershell", "-NonInteractive", "-Command",
             "Get-EventLog -LogName System -EntryType Error -Newest 3 -ErrorAction SilentlyContinue "
             "| Select-Object -ExpandProperty Message "
             "| ForEach-Object { $_.Substring(0, [Math]::Min(120, $_.Length)) }"],
            capture_output=True, text=True, timeout=12, creationflags=0x08000000,
        )
        if r.returncode == 0 and r.stdout.strip():
            lines.append("Erreurs récentes Windows:\n  " + r.stdout.strip()[:400].replace("\n", "\n  "))
    except Exception:
        pass

    return "\n".join(lines)


def list_processes(n: int = 10) -> str:
    """List top N processes by memory usage."""
    try:
        n = min(int(n), 25)
        procs = sorted(
            psutil.process_iter(["name", "cpu_percent", "memory_info", "pid", "status"]),
            key=lambda p: (p.info.get("memory_info") or type("", (), {"rss": 0})()).rss,
            reverse=True,
        )[:n]
        lines = [f"Top {n} processus (par RAM):"]
        for p in procs:
            try:
                rss = (p.info["memory_info"].rss // 1024**2) if p.info.get("memory_info") else 0
                cpu = p.info.get("cpu_percent") or 0
                lines.append(f"  [{p.info['pid']}] {p.info.get('name','?')}: RAM {rss}MB | CPU {cpu:.1f}%")
            except Exception:
                pass
        return "\n".join(lines)
    except Exception as e:
        return f"Erreur: {e}"


def get_weather(city: str) -> str:
    """Get current weather via open-meteo.com (free, no API key)."""
    if not isinstance(city, str) or not city.strip():
        return "Erreur: indiquez une ville."
    try:
        # Step 1: Geocode
        geo_url = (
            "https://nominatim.openstreetmap.org/search"
            f"?q={urllib.parse.quote(city.strip())}&format=json&limit=1"
        )
        req = urllib.request.Request(geo_url, headers={"User-Agent": "JARVIS-Local/2.0 kratos442500@gmail.com"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            geo = json.loads(resp.read())
        if not geo:
            return f"Ville introuvable: {city}"
        lat, lon = geo[0]["lat"], geo[0]["lon"]
        display_name = geo[0].get("display_name", city).split(",")[0]

        # Step 2: Weather
        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
            "wind_speed_10m,wind_direction_10m,weather_code,precipitation"
            "&wind_speed_unit=kmh&timezone=auto"
        )
        with urllib.request.urlopen(weather_url, timeout=8) as resp:
            data = json.loads(resp.read())

        cur = data["current"]
        temp = cur.get("temperature_2m", "?")
        feels = cur.get("apparent_temperature", "?")
        humidity = cur.get("relative_humidity_2m", "?")
        wind = cur.get("wind_speed_10m", "?")
        precip = cur.get("precipitation", 0)
        code = int(cur.get("weather_code", 0))
        condition = _WMO.get(code, f"Conditions météo {code}")

        precip_str = f" | Précipitations: {precip}mm" if precip else ""
        return (
            f"Météo à {display_name}: {condition}\n"
            f"Température: {temp}°C (ressenti {feels}°C)\n"
            f"Humidité: {humidity}% | Vent: {wind} km/h{precip_str}"
        )
    except Exception as e:
        logger.error(f"Erreur météo: {e}")
        return f"Erreur météo pour '{city}': {e}"


def get_news(topic: str = "", max_results: int = 5) -> str:
    """Get latest news via DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS  # type: ignore[import]
        query = topic.strip() if isinstance(topic, str) and topic.strip() else "actualités France"
        results = list(DDGS().news(query, max_results=min(int(max_results), 8)))
        if not results:
            return f"Aucune actualité trouvée pour: {topic}"
        header = f"Actualités — «{topic}»:" if topic else "Actualités générales:"
        lines = [header]
        for i, r in enumerate(results, 1):
            title = r.get("title", "Sans titre")
            body = (r.get("body") or "")[:200]
            source = r.get("source", "")
            date = (r.get("date") or "")[:10]
            lines.append(f"\n{i}. **{title}**\n   Source: {source} ({date})\n   {body}")
        return "\n".join(lines)
    except ImportError:
        return "Module duckduckgo-search manquant — pip install duckduckgo-search"
    except Exception as e:
        logger.error(f"Erreur actualités: {e}")
        return f"Erreur actualités: {e}"
