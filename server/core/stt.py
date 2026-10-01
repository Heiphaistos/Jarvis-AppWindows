from __future__ import annotations
import asyncio
import re
import numpy as np
from typing import TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("stt")

# Seuil bas : les micros portables capturent la parole vers RMS 0.01 — le VAD
# Silero + la blocklist d'hallucinations filtrent le vrai bruit en aval.
RMS_THRESHOLD = 0.005
# Seuil plus strict pour rejeter les segments sans parole
NO_SPEECH_THRESHOLD = 0.75
# Durée minimale de parole détectée (en secondes) pour déclencher la transcription
MIN_SPEECH_DURATION_S = 0.3

# Phrases que Whisper invente sur du silence ou du bruit (génériques de vidéos
# YouTube de son corpus d'entraînement). Comparées à la phrase ENTIÈRE, pas en
# sous-chaîne : « ouvre google.com » ou « traduction de hello » sont de vraies
# commandes et ne doivent plus disparaître.
_HALLUCINATION_RE = re.compile(
    r"^(?:"
    r"sous[- ]titr\w*\b.*|"
    r".*amara\.org.*|.*\bpatreon\b.*|"
    r"merci d'avoir regardé.*|merci (?:de|pour) votre attention.*|"
    r"(?:abonnez[- ]vous|like et abonne[- ]toi).*|"
    r"à bientôt pour une nouvelle vidéo|"
    r"transcription (?:par|réalisée) .*|traduction (?:par|réalisée) .*"
    r")[.!… ]*$",
    re.IGNORECASE,
)
# Signaux de confiance standard de Whisper (mêmes seuils que openai-whisper).
LOGPROB_THRESHOLD = -1.0        # en dessous : Whisper devine
COMPRESSION_RATIO_MAX = 2.4     # au-dessus : texte en boucle (« oui oui oui oui… »)
UNCERTAIN_LOGPROB = -0.6        # entre les deux : transcription gardée mais « incertaine »

def _stt_language() -> str:
    from utils.runtime_settings import setting
    return str(setting("voice.stt_language") or "fr")


_INITIAL_PROMPT = (
    "Commandes vocales en français adressées à JARVIS, assistant personnel de Monsieur : "
    "questions, météo, heure, calculs, rappels, fenêtres, NiTriTe, Discord, Spotify, Chrome."
)

# « Jarvis » mal entendu par Whisper → nom rétabli (aide aussi le routage).
_NAME_FIX = re.compile(r"\b(?:jar\s?vice|jarvice|jervis|jarvi|charvis|jarvisse|djarvis|jarvys|j\.a\.r\.v\.i\.s\.?)\b", re.IGNORECASE)


def clean_transcript(text: str) -> str:
    """Normalise une transcription : nom de JARVIS, espaces."""
    text = _NAME_FIX.sub("Jarvis", text or "")
    return re.sub(r"\s+", " ", text).strip()


def is_hallucination(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 2 or not re.search(r"[a-zA-ZÀ-ÿ0-9]", t):
        return True
    if _HALLUCINATION_RE.match(t):
        return True
    # Écho de la consigne initiale (fréquent sur du silence).
    if t.lower().startswith("commandes vocales en français"):
        return True
    # Même mot répété en boucle.
    words = re.findall(r"\w+", t.lower())
    return len(words) >= 6 and len(set(words)) <= 2


class STTManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._model: object | None = None
        self._lock = asyncio.Lock()

    def load(self) -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]
            from pathlib import Path
            model_ref = self._settings.whisper_model
            # Portable : si le dossier local n'existe pas, retomber sur le nom
            # de taille ("small") — faster-whisper le télécharge automatiquement
            # au premier lancement puis le met en cache.
            p = Path(model_ref)
            if not p.exists() and ("/" in model_ref or "\\" in model_ref):
                size = p.name.replace("faster-whisper-", "") or "small"
                logger.info(f"Modèle Whisper local absent — téléchargement de '{size}'...")
                model_ref = size
            # float16 n'est pas disponible partout (CPU, build compilé sans
            # CUDA pour CTranslate2) : retomber sur int8 plutôt que perdre le micro.
            wanted = self._settings.whisper_compute_type
            self._model = None
            for compute in dict.fromkeys((wanted, "int8")):
                try:
                    self._model = WhisperModel(
                        model_ref,
                        device=self._settings.whisper_device,
                        compute_type=compute,
                    )
                    break
                except (ValueError, RuntimeError) as e:
                    logger.warning(f"Whisper {compute} refusé ({e}) — essai suivant")
            if self._model is None:
                raise RuntimeError("aucun type de calcul Whisper accepté")
            logger.info(f"Whisper chargé: {model_ref} ({compute})")
        except Exception as e:
            logger.warning(f"STT non disponible: {e}")

    def unload(self) -> None:
        self._model = None

    @property
    def is_available(self) -> bool:
        return self._model is not None

    @staticmethod
    def _is_hallucination(text: str) -> bool:
        return is_hallucination(text)

    @staticmethod
    def prepare(chunks: list[list[float]], sample_rate: int) -> "np.ndarray | None":
        """Audio 16 kHz mono normalisé, ou None si ce n'est que du silence."""
        audio = np.concatenate([np.array(c, dtype=np.float32) for c in chunks])
        target_rate = 16000
        if sample_rate != target_rate:
            try:
                from math import gcd
                from scipy.signal import resample_poly  # type: ignore[import]
                g = gcd(target_rate, sample_rate)
                audio = resample_poly(audio, target_rate // g, sample_rate // g).astype(np.float32)
            except ImportError:
                # Version web (sans scipy) : le navigateur envoie déjà du 16 kHz ;
                # interpolation linéaire pour les autres cas.
                n = int(len(audio) * target_rate / sample_rate)
                audio = np.interp(
                    np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio
                ).astype(np.float32)
        rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0
        if rms < RMS_THRESHOLD:
            logger.debug(f"Audio ignoré (silence) — RMS={rms:.4f}")
            return None
        # Normaliser l'amplitude — micro Windows trop bas = Whisper qui hallucine.
        gain = min(0.1 / rms, 31.6)  # cible RMS 0,1, gain plafonné à ~30 dB
        return (audio * gain).clip(-1.0, 1.0)

    async def transcribe_audio(self, audio: "np.ndarray") -> tuple[str, bool]:
        """Whisper local → (texte, incertain)."""
        if self._model is None:
            return "", False

        def _run() -> tuple[str, bool]:
            segments, _info = self._model.transcribe(  # type: ignore[union-attr]
                audio,
                language=_stt_language(),
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
                initial_prompt=_INITIAL_PROMPT,
            )
            parts: list[str] = []
            uncertain = False
            for seg in segments:
                txt = seg.text.strip()
                if not txt:
                    continue
                if seg.no_speech_prob > NO_SPEECH_THRESHOLD:
                    logger.debug(f"Segment rejeté (no_speech={seg.no_speech_prob:.2f}): {txt!r}")
                    continue
                if seg.avg_logprob < LOGPROB_THRESHOLD or seg.compression_ratio > COMPRESSION_RATIO_MAX:
                    logger.debug(f"Segment rejeté (logprob={seg.avg_logprob:.2f}, "
                                 f"compression={seg.compression_ratio:.2f}): {txt!r}")
                    continue
                if is_hallucination(txt):
                    logger.debug(f"Hallucination rejetée: {txt!r}")
                    continue
                uncertain = uncertain or seg.avg_logprob < UNCERTAIN_LOGPROB
                parts.append(txt)
            return clean_transcript(" ".join(parts)), uncertain

        async with self._lock:
            return await asyncio.to_thread(_run)

    async def transcribe_chunks(self, chunks: list[list[float]], sample_rate: int) -> str:
        """Compatibilité : chunks bruts → texte (Whisper local)."""
        audio = await asyncio.to_thread(self.prepare, chunks, sample_rate)
        if audio is None:
            return ""
        text, _ = await self.transcribe_audio(audio)
        return text
