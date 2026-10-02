from __future__ import annotations
import asyncio
import time
import psutil
from utils.logger import get_logger

logger = get_logger("monitor")

CPU_WARN_PCT = 90
RAM_WARN_PCT = 90
DISK_WARN_PCT = 95
CHECK_INTERVAL = 30      # secondes entre chaque vérification
ALERT_COOLDOWN = 300     # 5 minutes minimum entre deux alertes du même type

_last_alerts: dict[str, float] = {}
_subscribers: set[asyncio.Queue] = set()

# Gardien VRAM (protection matériel) — callback async enregistré par main.py
VRAM_GUARD_PCT = 80.0
_VRAM_GUARD_TICKS = 4        # ~12 s au-dessus du plafond avant intervention
_vram_guardian = None
_vram_over_count = 0


def set_vram_guardian(callback) -> None:
    """Enregistre le protocole de rétrogradation (async callback(vram_pct))."""
    global _vram_guardian
    _vram_guardian = callback


def subscribe() -> asyncio.Queue:
    """Abonne un client WebSocket aux alertes. Retourne sa queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Désabonne un client."""
    _subscribers.discard(q)


def broadcast_direct(event_type: str, payload: dict) -> None:
    """Envoie immédiatement un événement à tous les abonnés, sans cooldown.

    Utilisé par main.py pour notifier que les modèles sont prêts.
    """
    item = {"type": event_type, "payload": payload}
    dead: set[asyncio.Queue] = set()
    for q in list(_subscribers):
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            dead.add(q)
    for q in dead:
        _subscribers.discard(q)


async def _broadcast(alert_type: str, message: str) -> None:
    """Envoie une alerte à tous les abonnés en respectant le cooldown."""
    now = time.monotonic()
    if now - _last_alerts.get(alert_type, 0) < ALERT_COOLDOWN:
        return
    _last_alerts[alert_type] = now

    payload = {"type": "system_alert", "payload": {"alert_type": alert_type, "message": message}}
    dead: set[asyncio.Queue] = set()
    for q in list(_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(q)
    for q in dead:
        _subscribers.discard(q)


async def _check_resources() -> None:
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    if cpu > CPU_WARN_PCT:
        await _broadcast("cpu_high", f"⚠️ CPU à {cpu:.0f}% — charge critique détectée.")

    if ram.percent > RAM_WARN_PCT:
        used_gb = ram.used / 1024 ** 3
        total_gb = ram.total / 1024 ** 3
        await _broadcast(
            "ram_high",
            f"⚠️ RAM saturée: {used_gb:.1f}/{total_gb:.1f} GB ({ram.percent:.0f}%)",
        )

    for part in psutil.disk_partitions():
        if part.fstype in ("", "squashfs", "tmpfs"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            if usage.percent > DISK_WARN_PCT:
                free_gb = usage.free / 1024 ** 3
                await _broadcast(
                    f"disk_full_{part.mountpoint}",
                    f"⚠️ Disque {part.mountpoint} presque plein: {usage.percent:.0f}% utilisé ({free_gb:.1f} GB libres)",
                )
        except (PermissionError, OSError):
            pass


def _gpu_stats() -> tuple[float, float] | None:
    """(utilisation %, VRAM %) via nvidia-smi, ou None sans GPU NVIDIA."""
    import subprocess
    from utils.platform import NO_WINDOW
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
            creationflags=NO_WINDOW,
        )
        if proc.returncode != 0:
            return None
        parts = proc.stdout.strip().split("\n")[0].split(",")
        util = float(parts[0])
        vram = float(parts[1]) / float(parts[2]) * 100
        return util, vram
    except Exception:
        return None


async def _push_metrics() -> None:
    """Métriques temps réel (CPU/RAM/GPU) poussées au HUD toutes les 3 s.
    Déclenche le protocole matériel si la VRAM reste au-dessus du plafond."""
    global _vram_over_count
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    gpu = await asyncio.to_thread(_gpu_stats)
    broadcast_direct("system_metrics", {
        "cpu": round(cpu, 1),
        "ram": round(ram, 1),
        "gpu": round(gpu[0], 1) if gpu else None,
        "vram": round(gpu[1], 1) if gpu else None,
    })

    if gpu is not None and _vram_guardian is not None:
        vram = gpu[1]
        if vram > VRAM_GUARD_PCT:
            _vram_over_count += 1
            if _vram_over_count >= _VRAM_GUARD_TICKS:
                _vram_over_count = 0
                try:
                    await _vram_guardian(vram)
                except Exception as e:
                    logger.error(f"Gardien VRAM en échec: {e}")
        else:
            _vram_over_count = 0


async def run_monitor() -> None:
    """Tâche asyncio background — métriques HUD (3 s) + alertes (30 s)."""
    logger.info("Moniteur système démarré")
    psutil.cpu_percent(interval=None)  # amorce la mesure non bloquante
    tick = 0
    while True:
        try:
            await asyncio.sleep(3)
            tick += 3
            if _subscribers:
                await _push_metrics()
            if tick >= CHECK_INTERVAL:
                tick = 0
                await _check_resources()
        except asyncio.CancelledError:
            logger.info("Moniteur système arrêté")
            break
        except Exception as e:
            logger.error(f"Erreur moniteur: {e}")
