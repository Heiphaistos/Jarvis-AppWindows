from __future__ import annotations
import asyncio
import subprocess
import base64
import tempfile
import re as _re
from pathlib import Path
from typing import TYPE_CHECKING
from utils.logger import get_logger

_SENTENCE_END = _re.compile(r'(?<=[.!?…»])\s+|(?<=[.!?…»])$')

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("tts")

MAX_TTS_CHARS = 1000


class TTSManager:
    def __init__(self, settings: "Settings") -> None:
        self._piper_exe = settings.piper_exe
        self._voice = settings.piper_voice
        self._available = self._piper_exe.exists() and self._voice.exists()
        if not self._available:
            logger.warning(
                "Piper TTS non disponible — placez piper.exe + voix .onnx dans server/models/piper/"
            )

    @property
    def is_available(self) -> bool:
        return self._available

    def set_voice(self, voice_path: Path) -> None:
        self._voice = voice_path
        self._available = self._piper_exe.exists() and voice_path.exists()
        logger.info(f"Voix TTS changée: {voice_path.name}")

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        """Découpe le texte en phrases sur ponctuation forte."""
        parts = _SENTENCE_END.split(text.strip())
        return [p.strip() for p in parts if p.strip()]

    async def synthesize(self, text: str) -> str | None:
        if not self._available:
            return None

        text = text[:MAX_TTS_CHARS]

        def _run() -> bytes:
            tmp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = Path(tmp.name)

                proc = subprocess.run(
                    [
                        str(self._piper_exe),
                        "--model",
                        str(self._voice),
                        "--output_file",
                        str(tmp_path),
                    ],
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
            return base64.b64encode(wav_bytes).decode()
        except Exception as e:
            logger.error(f"TTS synthèse échouée: {e}")
            return None
