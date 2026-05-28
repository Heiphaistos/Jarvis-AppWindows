from __future__ import annotations
import subprocess
import psutil
from utils.logger import get_logger

logger = get_logger("info_tools")


def _main_disk_usage() -> str:
    """Return disk usage for the first accessible partition."""
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            label = part.mountpoint.rstrip("/\\") or part.device
            return f"Disque {label}: {usage.used // 1024**3}/{usage.total // 1024**3} GB"
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
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 4:
                gpu_info = f"{parts[0]} | VRAM: {parts[1]}/{parts[2]} MB | Load: {parts[3]}%"
    except Exception:
        pass

    return (
        f"CPU: {cpu}% | "
        f"RAM: {mem.used // 1024**2}/{mem.total // 1024**2} MB ({mem.percent}%) | "
        f"{disk_str} | "
        f"GPU: {gpu_info}"
    )
