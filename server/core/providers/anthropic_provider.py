from __future__ import annotations
import json
from typing import AsyncGenerator, AsyncIterator

import httpx

from core.providers.http import shared_client
from core.providers.base import LLMProvider, ProviderError, parse_tool_args, tool_tag
from utils.logger import get_logger

logger = get_logger("provider.anthropic")

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
_API_VERSION = "2023-06-01"


async def parse_anthropic_sse(lines: AsyncIterator[str], label: str = "Anthropic") -> AsyncGenerator[str, None]:
    """Flux SSE Messages → texte ; chaque bloc tool_use devient une balise
    <JARVIS_TOOL> (appels parallèles exécutés ensemble par la boucle agent)."""
    tool: dict | None = None
    async for line in lines:
        if not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        if etype == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                tool = {"name": block.get("name", ""), "json": ""}
        elif etype == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "input_json_delta" and tool is not None:
                tool["json"] += delta.get("partial_json", "")
            else:
                text = delta.get("text")
                if text:
                    yield text
        elif etype == "content_block_stop" and tool is not None:
            yield tool_tag(tool["name"], parse_tool_args(tool["json"]))
            tool = None
        elif etype == "error":
            detail = (event.get("error") or {}).get("message", "erreur inconnue")
            raise ProviderError(f"{label}: {detail}")


class AnthropicProvider(LLMProvider):
    """API Messages Anthropic native (SSE) — cerveau Claude."""

    name = "anthropic"
    label = "Anthropic (Claude)"
    tier = "cloud"
    native_tools = True

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com") -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def is_available(self) -> bool:
        return bool(self._api_key and self._model)

    @property
    def model(self) -> str:
        return self._model

    def warm_target(self) -> tuple[str, dict[str, str]] | None:
        return f"{self._base_url}/v1/models", {"x-api-key": self._api_key, "anthropic-version": _API_VERSION}

    async def stream(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        payload: dict = {
            "model": self._model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = [
                {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                for t in tools
            ]
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        }

        try:
            # Connexion partagée (keep-alive) : pas de nouvelle poignée TLS à chaque message.
            async with shared_client().stream(
                "POST", f"{self._base_url}/v1/messages",
                json=payload, headers=headers, timeout=_TIMEOUT,
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")[:300]
                    raise ProviderError(f"{self.label} HTTP {resp.status_code}: {body}")
                async for piece in parse_anthropic_sse(resp.aiter_lines(), self.label):
                    yield piece
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.label} injoignable: {e}") from e
