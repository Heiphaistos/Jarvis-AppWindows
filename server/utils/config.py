from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from utils.hardware import detect_profile as _detect_profile, HardwareProfile

MODELS_DIR = Path(__file__).parents[1] / "models"


@lru_cache(maxsize=1)
def _get_profile() -> HardwareProfile:
    return _detect_profile()


_profile: HardwareProfile = _get_profile()


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765

    model_path: Path = MODELS_DIR / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
    n_ctx: int = 4096
    n_gpu_layers: int = _profile.n_gpu_layers
    n_threads: int = _profile.n_threads

    whisper_model: str = str(MODELS_DIR / f"faster-whisper-{_profile.whisper_model}")
    whisper_device: str = _profile.device
    whisper_compute_type: str = _profile.whisper_compute

    piper_exe: Path = MODELS_DIR / "piper" / "piper.exe"
    piper_voice: Path = MODELS_DIR / "piper" / "fr_FR-upmc-medium.onnx"

    max_context_messages: int = 20
    hw_profile: str = _profile.name

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
