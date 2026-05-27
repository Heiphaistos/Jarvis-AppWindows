from __future__ import annotations
from collections import deque


class ContextMemory:
    def __init__(self, max_messages: int) -> None:
        self._messages: deque[dict[str, str]] = deque(maxlen=max_messages)

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()
