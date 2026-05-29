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


def subscribe() -> asyncio.Queue:
    """Abonne un client WebSocket aux alertes. Retourne sa queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Désabonne un client."""
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
    cpu = psutil.cpu_percent(interval=1)
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


async def run_monitor() -> None:
    """Tâche asyncio background — surveille CPU/RAM/disque toutes les 30s."""
    logger.info("Moniteur système démarré")
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            await _check_resources()
        except asyncio.CancelledError:
            logger.info("Moniteur système arrêté")
            break
        except Exception as e:
            logger.error(f"Erreur moniteur: {e}")
