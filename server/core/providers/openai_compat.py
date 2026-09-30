from __future__ import annotations
import json
from typing import AsyncGenerator, AsyncIterator

import httpx

from core.providers.http import shared_client
from core.providers.base import LLMProvider, ProviderError, parse_tool_args, tool_tag
from utils.logger import get_logger

logger = get_logger("provider.openai_compat")

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


async def parse_openai_sse(lines: AsyncIterator[str]) -> AsyncGenerator[str, None]:
    """Flux SSE /chat/completions → texte, puis balise <JARVIS_TOOL> si le modèle
    appelle un outil (seul le 1er appel est gardé : la boucle agent en traite un
    par itération)."""
    calls: dict[int, dict[str, str]] = {}
    async for line in lines:
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if content:
            yield content
        for tc in delta.get("tool_calls") or []:
            slot = calls.setdefault(int(tc.get("index", 0)), {"name": "", "args": ""})
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["args"] += fn["arguments"]
    if calls:
        first = calls[min(calls)]
        if first["name"]:
            yield tool_tag(first["name"], parse_tool_args(first["args"]))


class OpenAICompatProvider(LLMProvider):
    """Toute API exposant /chat/completions au format OpenAI.

    Couvre : OpenAI, Google Gemini (endpoint openai/), Ollama, Groq, DeepSeek,
    xAI, OpenRouter, Mistral API, LM Studio, vLLM et tout endpoint custom.
    """

    tier = "cloud"

    def __init__(self, name: str, label: str, base_url: str, api_key: str, model: str,
                 native_tools: bool = False) -> None:
        self.name = name
        self.label = label
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self.native_tools = native_tools

    @property
    def is_available(self) -> bool:
        return bool(self._base_url and self._model)

    @property
    def model(self) -> str:
        return self._model

    def warm_target(self) -> tuple[str, dict[str, str]] | None:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        return f"{self._base_url}/models", headers

    async def stream(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        payload: dict = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools and self.native_tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            # Connexion partagée (keep-alive) : pas de nouvelle poignée TLS à chaque message.
            async with shared_client().stream(
                "POST", f"{self._base_url}/chat/completions",
                json=payload, headers=headers, timeout=_TIMEOUT,
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")[:300]
                    raise ProviderError(f"{self.label} HTTP {resp.status_code}: {body}")
                async for piece in parse_openai_sse(resp.aiter_lines()):
                    yield piece
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.label} injoignable: {e}") from e
