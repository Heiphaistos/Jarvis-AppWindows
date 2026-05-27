from __future__ import annotations
import subprocess
import psutil
from utils.logger import get_logger

logger = get_logger("info_tools")


def get_system_info() -> str:
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

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
        f"Disque C: {disk.used // 1024**3}/{disk.total // 1024**3} GB | "
        f"GPU: {gpu_info}"
    )
