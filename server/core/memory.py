from __future__ import annotations
from collections import deque


class ContextMemory:
    """Fenêtre de conversation d'une connexion.

    Les messages qui sortent de la fenêtre ne sont plus perdus : ils attendent
    dans `evicted` d'être condensés dans `summary` (résumé glissant), que le
    prompt réinjecte — JARVIS se souvient du début d'une longue discussion.
    """

    def __init__(self, max_messages: int) -> None:
        self._messages: deque[dict[str, str]] = deque(maxlen=max_messages)
        self.summary: str = ""
        self.evicted: list[dict[str, str]] = []
        self.user_turns: int = 0  # messages de Monsieur depuis le début de la session
        self.episode_id: int | None = None  # archive de cette session en mémoire persistante

    def _append(self, message: dict[str, str]) -> None:
        if self._messages.maxlen and len(self._messages) == self._messages.maxlen:
            self.evicted.append(self._messages[0])
        self._messages.append(message)

    def add_user(self, content: str) -> None:
        self.user_turns += 1
        self._append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self._append({"role": "assistant", "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def take_evicted(self) -> list[dict[str, str]]:
        out, self.evicted = self.evicted, []
        return out

    def clear(self) -> None:
        self._messages.clear()
        self.evicted.clear()
        self.summary = ""
        self.user_turns = 0
        self.episode_id = None  # nouvelle conversation → nouvel épisode

    def snapshot(self) -> "ContextMemory":
        """Copie figée (archivage en arrière-plan pendant que la conversation continue)."""
        copy = ContextMemory(self._messages.maxlen or 0)
        copy._messages.extend(self._messages)
        copy.summary, copy.user_turns, copy.episode_id = self.summary, self.user_turns, self.episode_id
        return copy
