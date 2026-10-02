from __future__ import annotations

import io
import wave

import numpy as np

from core.stt import clean_transcript, is_hallucination, _INITIAL_PROMPT
from utils.logger import get_logger

logger = get_logger("cloud_stt")

# Transcription dans le cloud quand une clé est configurée : Whisper large-v3
# (Groq, gratuit et ~0,3 s) ou gpt-4o-mini-transcribe (OpenAI) comprennent le
# français bien mieux que le Whisper « small » local sur CPU. Whisper local
# reste le secours (hors ligne, quota, clé absente). Le réglage
# « voice.cloud_stt » (ou JARVIS_CLOUD_STT=0) coupe l'envoi de l'audio vers le
# cloud ; « voice.stt_engine » force un moteur.
ENGINES = [
    # (provider, réglage du modèle, url de base par défaut)
    ("groq", "voice.groq_stt_model", "https://api.groq.com/openai/v1"),
    ("openai", "voice.openai_stt_model", "https://api.openai.com/v1"),
]
_TIMEOUT_S = 8.0


def enabled() -> bool:
    from utils.runtime_settings import setting
    return bool(setting("voice.cloud_stt")) and setting("voice.stt_engine") != "local"


def engines(providers) -> list[tuple[str, str, str, str]]:
    """Moteurs utilisables : (nom, modèle, url, clé) dans l'ordre de préférence."""
    if not enabled() or providers is None:
        return []
    from utils.runtime_settings import setting
    forced = setting("voice.stt_engine")
    out = []
    for name, model_key, default_url in ENGINES:
        if forced not in ("auto", name):
            continue
        model = setting(model_key)
        key = providers.api_key(name)
        if key:
            cfg_url = getattr(providers, "_configs", {}).get(name, {}).get("base_url") or default_url
            out.append((name, model, cfg_url.rstrip("/"), key))
    return out


def to_wav(audio: np.ndarray, rate: int = 16000) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _language() -> str:
    from utils.runtime_settings import setting
    return str(setting("voice.stt_language") or "fr")


async def transcribe(audio: np.ndarray, providers, client=None) -> str | None:
    """Texte transcrit par le premier moteur cloud qui répond, None si aucun."""
    candidates = engines(providers)
    if not candidates:
        return None
    import httpx
    from core.providers.http import shared_client
    http = client or shared_client()
    wav = to_wav(audio)
    for name, model, base_url, key in candidates:
        try:
            resp = await http.post(
                f"{base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data={"model": model, "language": _language(), "response_format": "json",
                      "temperature": "0", "prompt": _INITIAL_PROMPT},
                files={"file": ("voix.wav", wav, "audio/wav")},
                timeout=httpx.Timeout(_TIMEOUT_S),
            )
            resp.raise_for_status()
            text = clean_transcript(str(resp.json().get("text", "")))
        except Exception as e:
            logger.warning(f"Transcription {name} indisponible : {str(e)[:120]}")
            continue
        if is_hallucination(text):
            logger.debug(f"Transcription {name} rejetée : {text!r}")
            return ""
        logger.info(f"Transcription {name} ({model}) : {text!r}")
        return text
    return None
