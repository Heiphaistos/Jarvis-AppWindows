from __future__ import annotations
import asyncio
import numpy as np
from typing import TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("stt")


class STTManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._model: object | None = None

    def load(self) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]
            self._model = WhisperModel(
                self._settings.whisper_model,
                device=self._settings.whisper_device,
                compute_type=self._settings.whisper_compute_type,
            )
            logger.info(f"Whisper chargé: {self._settings.whisper_model}")
        except Exception as e:
            logger.warning(f"STT non disponible: {e}")

    @property
    def is_available(self) -> bool:
        return self._model is not None

    async def transcribe_chunks(
        self, chunks: list[list[float]], sample_rate: int
    ) -> str:
        if self._model is None:
            return ""

        def _run() -> str:
            audio = np.concatenate(
                [np.array(c, dtype=np.float32) for c in chunks]
            )
            segments, _ = self._model.transcribe(  # type: ignore[union-attr]
                audio, language="fr", beam_size=5
            )
            return " ".join(s.text.strip() for s in segments)

        return await asyncio.to_thread(_run)
