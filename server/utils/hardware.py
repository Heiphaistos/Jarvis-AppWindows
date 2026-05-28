from __future__ import annotations
import subprocess
import os
from dataclasses import dataclass, replace
from utils.logger import get_logger

logger = get_logger("hardware")


@dataclass(frozen=True)
class HardwareProfile:
    name: str           # identifiant lisible
    device: str         # "cuda" | "cpu"
    vram_mb: int        # VRAM détectée (0 si CPU)
    n_gpu_layers: int   # -1 = tout sur GPU, 0 = CPU
    n_threads: int      # threads CPU pour LLM / STT
    whisper_model: str  # "tiny" | "small" | "medium"
    whisper_compute: str  # "float16" | "int8"
    llm_max_vram_mb: int  # budget VRAM alloué au LLM


_NVIDIA_HIGH = HardwareProfile(
    name="nvidia_high",
    device="cuda", vram_mb=0,
    n_gpu_layers=-1,
    n_threads=8,
    whisper_model="medium",
    whisper_compute="float16",
    llm_max_vram_mb=18_000,
)

_NVIDIA_MEDIUM = HardwareProfile(
    name="nvidia_medium",
    device="cuda", vram_mb=0,
    n_gpu_layers=28,
    n_threads=8,
    whisper_model="small",
    whisper_compute="float16",
    llm_max_vram_mb=4_800,
)

_NVIDIA_LOW = HardwareProfile(
    name="nvidia_low",
    device="cuda", vram_mb=0,
    n_gpu_layers=16,
    n_threads=8,
    whisper_model="tiny",
    whisper_compute="float16",
    llm_max_vram_mb=3_000,
)

_CPU_HIGHEND = HardwareProfile(
    name="cpu_highend",
    device="cpu", vram_mb=0,
    n_gpu_layers=0,
    n_threads=16,
    whisper_model="medium",
    whisper_compute="int8",
    llm_max_vram_mb=0,
)

_CPU_STANDARD = HardwareProfile(
    name="cpu_standard",
    device="cpu", vram_mb=0,
    n_gpu_layers=0,
    n_threads=8,
    whisper_model="small",
    whisper_compute="int8",
    llm_max_vram_mb=0,
)


def _nvidia_vram() -> tuple[str, int] | None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return None
        line = r.stdout.strip().split("\n")[0]
        parts = line.split(",")
        if len(parts) < 2:
            return None
        return parts[0].strip(), int(parts[1].strip())
    except Exception as e:
        logger.debug(f"nvidia-smi indisponible: {e}")
        return None


def _cpu_thread_count() -> int:
    return max(4, os.cpu_count() or 4)


def detect_profile() -> HardwareProfile:
    nvidia = _nvidia_vram()
    if nvidia:
        name, vram_mb = nvidia
        if vram_mb >= 16_000:
            profile = _NVIDIA_HIGH
        elif vram_mb >= 7_000:
            profile = _NVIDIA_MEDIUM
        else:
            profile = _NVIDIA_LOW
        profile = replace(profile, vram_mb=vram_mb)
        logger.info(
            f"Profil {profile.name!r} — GPU: {name} "
            f"({vram_mb} MB) · Whisper: {profile.whisper_model} · "
            f"GPU layers: {profile.n_gpu_layers}"
        )
        return profile

    threads = _cpu_thread_count()
    profile = _CPU_HIGHEND if threads >= 16 else _CPU_STANDARD
    logger.info(
        f"Profil {profile.name!r} — CPU ({threads} threads) · "
        f"Whisper: {profile.whisper_model} · device: cpu"
    )
    return profile
