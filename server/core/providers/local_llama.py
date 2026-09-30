from __future__ import annotations
from typing import AsyncGenerator, TYPE_CHECKING
from core.providers.base import LLMProvider

if TYPE_CHECKING:
    from core.llm import LLMManager


class LocalLlamaProvider(LLMProvider):
    """Mistral GGUF local via llama-cpp — le cerveau par défaut, 100 % hors-ligne."""

    name = "local"
    label = "Local (Mistral GGUF)"
    tier = "local"

    def __init__(self, manager: "LLMManager") -> None:
        self._manager = manager

    @property
    def is_available(self) -> bool:
        return self._manager.is_available

    @property
    def model(self) -> str:
        return self._manager.model_name

    async def stream(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        async for token in self._manager.stream(messages, max_tokens=max_tokens, system=system):
            yield token
