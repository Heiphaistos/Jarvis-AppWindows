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
        self._text: dict[int, _Counter] = defaultdict(_Counter)
        self._audio: dict[int, _Counter] = defaultdict(_Counter)

    def allow_text(self, ws_id: int) -> bool:
        allowed = self._text[ws_id].is_allowed(
            time.monotonic(), _TEXT_QUERY_MAX, _TEXT_QUERY_WINDOW
        )
        if not allowed:
            logger.warning(f"Rate limit text_query ws={ws_id}")
        return allowed

    def allow_audio(self, ws_id: int) -> bool:
        return self._audio[ws_id].is_allowed(
            time.monotonic(), _AUDIO_CHUNK_MAX, _AUDIO_CHUNK_WINDOW
        )

    def cleanup(self, ws_id: int) -> None:
        self._text.pop(ws_id, None)
        self._audio.pop(ws_id, None)
