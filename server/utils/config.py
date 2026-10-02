from __future__ import annotations
from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from utils.hardware import detect_profile as _detect_profile, HardwareProfile

import os as _os, sys as _sys

def _resolve_models_dir() -> Path:
    # 1. Variable d'environnement (injectée par JARVIS.exe au lancement)
    env = _os.environ.get("JARVIS_MODELS_DIR")
    if env:
        return Path(env)
    # 2. PyInstaller frozen — models/ à côté de l'exe (Windows) ; sous Linux
    #    l'exe est en lecture seule → ~/.local/share/JARVIS/models
    if getattr(_sys, "frozen", False):
        if _sys.platform == "win32":
            return Path(_sys.executable).parent / "models"
        xdg = _os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        return Path(xdg) / "JARVIS" / "models"
    # 3. Dev — server/../models
    return Path(__file__).parents[1] / "models"

MODELS_DIR = _resolve_models_dir()


def _default_web_dir() -> Path:
    """Interface web compilée (client/dist) servie en mode panneau web / hébergé."""
    if getattr(_sys, "frozen", False):
        beside = Path(_sys.executable).parent / "web"
        if beside.is_dir():
            return beside
        return Path(getattr(_sys, "_MEIPASS", beside.parent)) / "web"
    return Path(__file__).parents[2] / "client" / "dist"


@lru_cache(maxsize=1)
def _get_profile() -> HardwareProfile:
    return _detect_profile()


_profile: HardwareProfile = _get_profile()


class Settings(BaseSettings):
    host: str = Field("127.0.0.1", validation_alias=AliasChoices("JARVIS_HOST", "HOST"))
    port: int = Field(8765, validation_alias=AliasChoices("JARVIS_PORT", "PORT"))

    # desktop : application Tauri (défaut) · agent : panneau web local, comme
    # NiTriTe Agent · hosted : version web sur un serveur (VPS), sans accès au PC.
    mode: str = Field("desktop", validation_alias="JARVIS_MODE")
    web_dir: Path = Field(default_factory=_default_web_dir, validation_alias="JARVIS_WEB_DIR")
    # Mode hébergé : mot de passe d'accès et adresse publique (https://…).
    password: str = Field("", validation_alias="JARVIS_PASSWORD")
    public_origin: str = Field("", validation_alias="JARVIS_PUBLIC_ORIGIN")
    # Derrière nginx/Caddy : faire confiance à X-Forwarded-For / -Proto.
    trust_proxy: bool = Field(False, validation_alias="JARVIS_TRUST_PROXY")
    # False : ni LLM local ni Whisper local (serveur sans GPU, cerveaux cloud).
    local_models: bool = Field(True, validation_alias="JARVIS_LOCAL_MODELS")

    model_path: Path = MODELS_DIR / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
    n_ctx: int = 8192
    n_gpu_layers: int = _profile.n_gpu_layers
    n_threads: int = _profile.n_threads

    whisper_model: str = str(MODELS_DIR / f"faster-whisper-{_profile.whisper_model}")
    # En mode PyInstaller, cublas64_12.dll n'est pas disponible — STT tourne sur CPU (int8)
    whisper_device: str = "cpu" if getattr(_sys, "frozen", False) else _profile.device
    whisper_compute_type: str = "int8" if getattr(_sys, "frozen", False) else _profile.whisper_compute

    piper_exe: Path = MODELS_DIR / "piper" / ("piper.exe" if _sys.platform == "win32" else "piper")
    # Voix par défaut : UPMC = masculine française classique (la plus « JARVIS »).
    # Doit rester alignée avec selectedVoice par défaut côté client.
    piper_voice: Path = MODELS_DIR / "piper" / "fr_FR-upmc-medium.onnx"

    max_context_messages: int = 30
    hw_profile: str = _profile.name

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", populate_by_name=True, extra="ignore",
    )


settings = Settings()
