from __future__ import annotations
import asyncio
import numpy as np
from typing import TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("stt")

# Seuil RMS relevé : le micro WASAPI capture à volume plus élevé qu'un stream WebView2
RMS_THRESHOLD = 0.02
# Seuil plus strict pour rejeter les segments sans parole
NO_SPEECH_THRESHOLD = 0.75
# Durée minimale de parole détectée (en secondes) pour déclencher la transcription
MIN_SPEECH_DURATION_S = 0.3

HALLUCINATION_PHRASES = {
    "amara.org", "sous-titres", "sous-titrage", "transcription",
    "merci d'avoir regardé", "à bientôt", "sous-titré par",
    "traduction", "traducteur", "www.", ".com", ".org",
    "sous-titres réalisés", "patreon", "merci de votre attention",
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
        t = text.lower().strip()
        if len(t) < 3:
            return True
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

            # Resampler à 16kHz si le sample rate natif est différent
            target_rate = 16000
            if sample_rate != target_rate:
                from math import gcd
                from scipy.signal import resample_poly  # type: ignore[import]
                g = gcd(target_rate, sample_rate)
                audio = resample_poly(audio, target_rate // g, sample_rate // g).astype(np.float32)
                logger.debug(f"Resampled {sample_rate}→{target_rate} Hz ({len(audio)} samples)")

            rms = float(np.sqrt(np.mean(audio ** 2)))
            logger.debug(f"Audio RMS={rms:.4f} (seuil={RMS_THRESHOLD})")
            if rms < RMS_THRESHOLD:
                logger.debug(f"Audio ignoré (silence) — RMS={rms:.4f}")
                return ""

            # Normaliser l'amplitude — si micro Windows trop bas, Whisper hallucine
            # Target RMS 0.1 (parole correcte), gain plafonné à +30 dB
            target_rms = 0.1
            gain = min(target_rms / rms, 31.6)  # max ~30 dB
            audio = (audio * gain).clip(-1.0, 1.0)
            logger.debug(f"Gain appliqué: x{gain:.2f} (RMS {rms:.4f}→{target_rms:.4f})")

            segments, info = self._model.transcribe(  # type: ignore[union-attr]
                audio,
                language="fr",
                beam_size=5,
                best_of=1,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 100,
                    "min_speech_duration_ms": int(MIN_SPEECH_DURATION_S * 1000),
                },
                no_speech_threshold=NO_SPEECH_THRESHOLD,
                condition_on_previous_text=False,  # évite les hallucinations chaînées
                temperature=0.0,                   # décodage greedy pur — plus stable
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
