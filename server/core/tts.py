from __future__ import annotations
import re
import asyncio
import subprocess
import base64
import tempfile
import time
import re as _re
from pathlib import Path
import io
import os
import wave
from typing import TYPE_CHECKING, Callable
from utils.logger import get_logger

_SENTENCE_END = _re.compile(r'(?<=[.!?…»])\s+|(?<=[.!?…»])$')

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("tts")

MAX_TTS_CHARS = 1000

# Voix masculines connues dans les modèles Piper multi-locuteurs
_MALE_SPEAKERS = {"pierre", "tom", "gilles", "male"}


def _male_speaker_id(voice_path: Path) -> int | None:
    """ID du locuteur masculin d'un modèle multi-speakers, sinon None.

    fr_FR-upmc-medium contient jessica (0, défaut Piper !) et pierre (1) —
    sans --speaker, Piper parle avec la voix féminine.
    """
    import json
    config_path = Path(str(voice_path) + ".json")
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        if int(cfg.get("num_speakers", 1)) <= 1:
            return None
        speaker_map: dict[str, int] = cfg.get("speaker_id_map", {})
        for name, sid in speaker_map.items():
            if name.lower() in _MALE_SPEAKERS:
                return int(sid)
    except Exception:
        pass
    return None


# Gemini TTS : voix neurales expressives, pilotables par une consigne de ton.
# Voix masculines graves adaptées à JARVIS : Charon, Orus, Iapetus, Algenib…
GEMINI_TTS_MODEL = os.environ.get("JARVIS_GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")


def _gemini_tts_model() -> str:
    from utils.runtime_settings import setting
    return str(setting("tts.gemini_model") or GEMINI_TTS_MODEL)
GEMINI_TTS_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_VOICES = ("Charon", "Orus", "Iapetus", "Algenib", "Alnilam", "Rasalgethi", "Sadaltager", "Schedar")
# Consigne de ton : réglage tts.gemini_style (Paramètres › Moteurs).


def _gemini_tts_style() -> str:
    from utils.runtime_settings import setting
    return str(setting("tts.gemini_style"))


def pcm_to_wav(pcm: bytes, rate: int = 24000, channels: int = 1, width: int = 2) -> bytes:
    """Enveloppe du PCM 16 bits brut (sortie Gemini) dans un WAV décodable par WebAudio."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


_MD_LINK = re.compile(r"\[([^\]]+)\]\((?:https?://)?[^)]+\)")
_URL = re.compile(r"https?://\S+|www\.\S+")
_CITATION = re.compile(r"\s?\[\d+(?:\s*[,–-]\s*\d+)*\]")
_CODE_BLOCK = re.compile(r"```.*?(?:```|$)", re.S)


def speakable(text: str) -> str:
    """Texte à prononcer : sans markdown, citations [n], URL ni blocs de code.

    Les réponses écrites (recherche, synthèse) gardent leur mise en forme à
    l'écran ; la voix ne lit ni « astérisque » ni « crochet un ».
    """
    t = _CODE_BLOCK.sub(" le code est affiché à l'écran. ", text or "")
    t = _MD_LINK.sub(r"\1", t)
    t = _URL.sub("", t)
    t = _CITATION.sub("", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"(\*\*|__|\*|~~)", "", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)          # titres
    t = re.sub(r"^\s*(?:[-*•+]|\d+[.)])\s+", "", t, flags=re.M)  # puces et listes
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)                     # citations
    t = re.sub(r"^\s*\|?[\s:|-]+\|?\s*$", "", t, flags=re.M)    # séparateurs de tableau
    t = t.replace("|", ", ")
    t = re.sub(r"\s+", " ", t).strip(" ,")
    return t if re.search(r"[A-Za-zÀ-ÿ0-9]", t) else ""


DEFAULT_EDGE_VOICE = "fr-FR-HenriNeural"


class TTSManager:
    """Deux moteurs : Edge-TTS (voix neurales naturelles, en ligne) et Piper
    (local). Si la voix active est Edge et que le réseau échoue, bascule
    automatiquement sur Piper — JARVIS ne devient jamais muet."""

    _EDGE_COOLDOWN_S = 60.0  # après un échec, rester sur Piper (voix cohérente)

    def __init__(self, settings: "Settings") -> None:
        self._piper_exe = settings.piper_exe
        self._voice = settings.piper_voice
        self._speaker: int | None = _male_speaker_id(settings.piper_voice)
        self._edge_voice: str | None = None
        self._edge_down_until: float = 0.0
        self._gemini_voice: str | None = None
        self._gemini_down_until: float = 0.0
        self._gemini_key: Callable[[], str] = lambda: ""
        self._piper_ok = self._piper_exe.exists() and self._voice.exists()
        if not self._piper_ok:
            # Sans voix locale (Linux sans Piper, serveur web) : voix neurale en
            # ligne Henri plutôt qu'un JARVIS muet.
            self._edge_voice = DEFAULT_EDGE_VOICE
            logger.warning(
                f"Piper TTS non disponible ({self._piper_exe.parent}) — voix en ligne {DEFAULT_EDGE_VOICE}"
            )

    @property
    def is_available(self) -> bool:
        return self._piper_ok or self._edge_voice is not None or self._gemini_voice is not None

    def set_key_provider(self, getter: Callable[[], str]) -> None:
        """Source de la clé Gemini (celle du cerveau Gemini, stockée côté serveur)."""
        self._gemini_key = getter

    def set_gemini_voice(self, voice_name: str) -> None:
        """Active une voix Gemini TTS ; Edge Henri puis Piper servent de secours."""
        self.set_edge_voice("fr-FR-HenriNeural")  # secours masculin cohérent
        self._gemini_voice = voice_name
        self._gemini_down_until = 0.0
        logger.info(f"Voix TTS : Gemini {voice_name} (secours Edge Henri puis Piper)")

    async def _synthesize_gemini(self, text: str) -> str:
        import httpx
        key = self._gemini_key()
        if not key:
            raise RuntimeError("clé Gemini absente (onglet CERVEAU)")
        payload = {
            "contents": [{"parts": [{"text": f"{_gemini_tts_style()}{text}"}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self._gemini_voice}}},
            },
        }
        from core.providers.http import shared_client
        resp = await shared_client().post(
            GEMINI_TTS_URL.format(model=_gemini_tts_model()), json=payload,
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini TTS HTTP {resp.status_code}: {resp.text[:200]}")
        part = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        mime = str(part.get("mimeType", ""))
        rate = int(_re.search(r"rate=(\d+)", mime).group(1)) if "rate=" in mime else 24000
        return base64.b64encode(pcm_to_wav(base64.b64decode(part["data"]), rate=rate)).decode()

    def set_voice(self, voice_path: Path) -> None:
        self._edge_voice = None
        self._gemini_voice = None
        self._voice = voice_path
        self._speaker = _male_speaker_id(voice_path)
        self._piper_ok = self._piper_exe.exists() and voice_path.exists()
        if not self._piper_ok:
            self._edge_voice = DEFAULT_EDGE_VOICE  # voix locale absente : rester audible
        logger.info(f"Voix TTS changée: {voice_path.name} (speaker={self._speaker})")

    def set_edge_voice(self, voice_name: str) -> None:
        """Active une voix neurale Edge-TTS (ex. fr-FR-HenriNeural)."""
        self._gemini_voice = None
        self._edge_voice = voice_name
        # Le secours Piper doit rester cohérent avec la voix Edge (masculine) —
        # jamais de bascule vers une voix féminine choisie précédemment.
        default_male = self._piper_exe.parent / "fr_FR-upmc-medium.onnx"
        if default_male.exists():
            self._voice = default_male
            self._speaker = _male_speaker_id(default_male)
            self._piper_ok = self._piper_exe.exists()
        logger.info(f"Voix TTS changée: {voice_name} (Edge, secours Piper {self._voice.stem})")

    async def _synthesize_edge(self, text: str) -> str:
        import edge_tts  # type: ignore[import]
        communicate = edge_tts.Communicate(text, self._edge_voice)
        buf = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        if not buf:
            raise RuntimeError("Edge-TTS: flux audio vide")
        return base64.b64encode(buf).decode()  # MP3 — décodé par WebAudio côté client

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        """Découpe le texte en phrases sur ponctuation forte."""
        parts = _SENTENCE_END.split(text.strip())
        return [p.strip() for p in parts if p.strip()]

    async def synthesize(self, text: str) -> str | None:
        if not self.is_available:
            return None

        text = speakable(text)[:MAX_TTS_CHARS]
        if not text:
            return None  # que de la mise en forme (ligne de tableau, séparateur…)

        if self._gemini_voice is not None and time.monotonic() >= self._gemini_down_until:
            try:
                return await asyncio.wait_for(self._synthesize_gemini(text), timeout=12)
            except Exception as e:
                # Quota, clé absente ou réseau : Edge/Piper pendant 2 min, voix cohérente.
                self._gemini_down_until = time.monotonic() + 120.0
                logger.warning(f"Gemini TTS indisponible ({e}) — secours Edge/Piper 2 min")

        if self._edge_voice is not None and time.monotonic() >= self._edge_down_until:
            # 2 tentatives : Microsoft coupe parfois les connexions en rafale
            # (une par phrase) — un retry absorbe la quasi-totalité des échecs.
            for attempt in (1, 2):
                try:
                    audio = await asyncio.wait_for(self._synthesize_edge(text), timeout=10)
                    logger.debug(f"TTS Edge OK: {len(text)} chars")
                    return audio
                except Exception as e:
                    if attempt == 1:
                        await asyncio.sleep(0.4)
                        continue
                    # Cooldown : voix Piper cohérente pendant 60 s plutôt
                    # qu'une alternance Henri/Piper phrase par phrase.
                    self._edge_down_until = time.monotonic() + self._EDGE_COOLDOWN_S
                    logger.warning(f"Edge-TTS en panne ({e}) — Piper pendant 60 s")
            if not self._piper_ok:
                return None

        def _run() -> bytes:
            tmp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = Path(tmp.name)

                cmd = [
                    str(self._piper_exe),
                    "--model", str(self._voice),
                    "--output_file", str(tmp_path),
                ]
                if self._speaker is not None:
                    cmd += ["--speaker", str(self._speaker)]
                proc = subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    capture_output=True,
                    timeout=30,
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"Piper error: {proc.stderr.decode()}")
                return tmp_path.read_bytes()
            finally:
                if tmp_path is not None:
                    tmp_path.unlink(missing_ok=True)

        try:
            wav_bytes = await asyncio.to_thread(_run)
            logger.debug(f"TTS OK: {len(wav_bytes)} bytes pour {len(text)} chars")
            return base64.b64encode(wav_bytes).decode()
        except Exception as e:
            logger.error(f"TTS synthèse échouée: {e}")
            return None
