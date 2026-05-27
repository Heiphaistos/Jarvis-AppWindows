from __future__ import annotations
import asyncio
import subprocess
import base64
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("tts")


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

    async def synthesize(self, text: str) -> str | None:
        if not self._available:
            return None

        def _run() -> bytes:
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
            data = tmp_path.read_bytes()
            tmp_path.unlink(missing_ok=True)
            return data

        try:
            wav_bytes = await asyncio.to_thread(_run)
            return base64.b64encode(wav_bytes).decode()
        except Exception as e:
            logger.error(f"TTS synthèse échouée: {e}")
            return None
