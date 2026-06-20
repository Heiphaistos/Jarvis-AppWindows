from __future__ import annotations
import time
from collections import defaultdict
from utils.logger import get_logger

logger = get_logger("rate_limiter")

_TEXT_QUERY_MAX = 20
_TEXT_QUERY_WINDOW = 60.0
_AUDIO_CHUNK_MAX = 300
_AUDIO_CHUNK_WINDOW = 60.0


class _Counter:
    __slots__ = ("timestamps",)

    def __init__(self) -> None:
        self.timestamps: list[float] = []

    def is_allowed(self, now: float, max_count: int, window: float) -> bool:
        cutoff = now - window
        self.timestamps = [t for t in self.timestamps if t >= cutoff]
        if len(self.timestamps) >= max_count:
            return False
        self.timestamps.append(now)
        return True


class RateLimiter:
    def __init__(self) -> None:
        self._text: dict[str, _Counter] = defaultdict(_Counter)
        self._audio: dict[str, _Counter] = defaultdict(_Counter)

    @staticmethod
    def _get_key(ws: object) -> str:
        """Retourne l'adresse IP du client comme clé de rate-limit.

        Utilise l'IP plutôt que id(ws) pour que plusieurs connexions
        depuis la même IP partagent le même bucket.
        """
        return getattr(ws, "remote_address", ("unknown",))[0]

    def allow_text(self, ws: object) -> bool:
        key = self._get_key(ws)
        allowed = self._text[key].is_allowed(
            time.monotonic(), _TEXT_QUERY_MAX, _TEXT_QUERY_WINDOW
        )
        if not allowed:
            logger.warning(f"Rate limit text_query ip={key}")
        return allowed

    def allow_audio(self, ws: object) -> bool:
        key = self._get_key(ws)
        return self._audio[key].is_allowed(
            time.monotonic(), _AUDIO_CHUNK_MAX, _AUDIO_CHUNK_WINDOW
        )

    def cleanup(self, ws: object) -> None:
        key = self._get_key(ws)
        self._text.pop(key, None)
        self._audio.pop(key, None)
