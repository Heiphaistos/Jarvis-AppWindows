from pydantic_settings import BaseSettings
from pathlib import Path

MODELS_DIR = Path(__file__).parents[1] / "models"


class Settings(BaseSettings):
    # Server
    host: str = "127.0.0.1"
    port: int = 8765

    # LLM
    model_path: Path = MODELS_DIR / "mistral-7b-instruct-v0.3.Q4_K_M.gguf"
    n_ctx: int = 4096
    n_gpu_layers: int = 35
    n_threads: int = 8

    # STT
    whisper_model: str = "small"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # TTS
    piper_exe: Path = MODELS_DIR / "piper" / "piper.exe"
    piper_voice: Path = MODELS_DIR / "piper" / "en_US-lessac-high.onnx"

    # Wake Word
    wake_word_model: str = "jarvis"
    wake_word_threshold: float = 0.5

    # Memory
    max_context_messages: int = 20

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
