from __future__ import annotations
import asyncio
import numpy as np
from typing import TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("stt")

RMS_THRESHOLD = 0.005
NO_SPEECH_THRESHOLD = 0.6
HALLUCINATION_PHRASES = {
    "amara.org", "sous-titres", "sous-titrage", "transcription",
    "merci d'avoir regardé", "à bientôt", "sous-titré par",
    "traduction", "traducteur", "www.", ".com", ".org",
}


class STTManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._model: object | None = None
        self._lock = asyncio.Lock()

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

    @staticmethod
    def _is_hallucination(text: str) -> bool:
        t = text.lower()
        return any(phrase in t for phrase in HALLUCINATION_PHRASES)

    async def transcribe_chunks(
        self, chunks: list[list[float]], sample_rate: int
    ) -> str:
        if self._model is None:
            return ""

        def _run() -> str:
            audio = np.concatenate(
                [np.array(c, dtype=np.float32) for c in chunks]
            )
            rms = float(np.sqrt(np.mean(audio ** 2)))
            if rms < RMS_THRESHOLD:
                logger.debug(f"Audio ignoré (silence) — RMS={rms:.4f}")
                return ""

            segments, _ = self._model.transcribe(  # type: ignore[union-attr]
                audio,
                language="fr",
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
                no_speech_threshold=NO_SPEECH_THRESHOLD,
            )

            result_parts: list[str] = []
            for seg in segments:
                txt = seg.text.strip()
                if not txt:
                    continue
                if seg.no_speech_prob > NO_SPEECH_THRESHOLD:
                    logger.debug(f"Segment rejeté (no_speech={seg.no_speech_prob:.2f}): {txt!r}")
                    continue
                if STTManager._is_hallucination(txt):
                    logger.debug(f"Hallucination rejetée: {txt!r}")
                    continue
                result_parts.append(txt)

            return " ".join(result_parts)

        async with self._lock:
            return await asyncio.to_thread(_run)
