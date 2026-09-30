from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Any, Awaitable, Callable

import numpy as np

from utils.logger import get_logger

logger = get_logger("live")

# Gemini Live : conversation vocale temps réel (audio → audio), interruptions,
# appels d'outils. Modèle et point d'accès réglables (les noms évoluent vite).
LIVE_URL = os.environ.get(
    "JARVIS_LIVE_URL",
    "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent",
)
LIVE_MODEL = os.environ.get("JARVIS_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-09-2025")
INPUT_RATE = 16000
OUTPUT_RATE = 24000

Send = Callable[[str, dict], Awaitable[None]]
RunTool = Callable[[str, dict], Awaitable[str]]


def to_pcm16(samples: list[float] | np.ndarray, rate: int) -> bytes:
    """Échantillons flottants [-1, 1] au taux `rate` → PCM 16 bits mono 16 kHz."""
    x = np.asarray(samples, dtype=np.float32)
    if rate != INPUT_RATE and x.size:
        n = max(1, int(round(x.size * INPUT_RATE / rate)))
        x = np.interp(np.linspace(0, x.size - 1, n), np.arange(x.size), x).astype(np.float32)
    return (np.clip(x, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def gemini_function_declarations(schemas: list[dict]) -> list[dict]:
    """Schémas des outils JARVIS → déclarations Gemini (types en majuscules, sans `default`)."""
    def conv(schema: dict) -> dict:
        out: dict[str, Any] = {"type": str(schema.get("type", "string")).upper()}
        if "description" in schema:
            out["description"] = schema["description"]
        if "properties" in schema:
            out["properties"] = {k: conv(v) for k, v in schema["properties"].items()}
        if schema.get("required"):
            out["required"] = list(schema["required"])
        if "items" in schema:
            out["items"] = conv(schema["items"])
        return out

    decls = []
    for s in schemas:
        d = {"name": s["name"], "description": s["description"]}
        params = s.get("parameters") or {}
        if params.get("properties"):
            d["parameters"] = conv(params)
        decls.append(d)
    return decls


class LiveSession:
    """Session Gemini Live reliée à un client JARVIS.

    Évènements envoyés au client via `send` :
      live_state {active, error?} · live_audio {audio (PCM16 base64), rate}
      live_transcript {role: user|assistant, text} · live_interrupted · live_turn_complete
      agent_step / tool_result pendant les appels d'outils.
    """

    def __init__(self, api_key: str, send: Send, run_tool: RunTool, system: str,
                 tools: list[dict] | None = None, voice: str = "Charon",
                 model: str = LIVE_MODEL, url: str = LIVE_URL, connect=None) -> None:
        self._key = api_key
        self._send = send
        self._run_tool = run_tool
        self._system = system
        self._tools = tools or []
        self._voice = voice
        self._model = model
        self._url = url
        self._connect = connect
        self._ws = None
        self._reader: asyncio.Task | None = None
        self.active = False

    async def start(self) -> None:
        if self._connect is None:
            import websockets
            self._connect = websockets.connect
        self._ws = await self._connect(f"{self._url}?key={self._key}", max_size=None)
        setup: dict[str, Any] = {
            "model": f"models/{self._model}",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self._voice}}},
            },
            "systemInstruction": {"parts": [{"text": self._system}]},
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
        }
        if self._tools:
            setup["tools"] = [{"functionDeclarations": gemini_function_declarations(self._tools)}]
        await self._ws.send(json.dumps({"setup": setup}))
        first = json.loads(await asyncio.wait_for(self._ws.recv(), timeout=10))
        if "setupComplete" not in first:
            raise RuntimeError(f"Gemini Live a refusé la session : {str(first)[:200]}")
        self.active = True
        self._reader = asyncio.create_task(self._read_loop())
        await self._send("live_state", {"active": True, "model": self._model, "voice": self._voice})

    async def send_audio(self, samples: list[float], rate: int) -> None:
        if not self.active or self._ws is None:
            return
        data = base64.b64encode(to_pcm16(samples, rate)).decode()
        await self._ws.send(json.dumps({
            "realtimeInput": {"audio": {"data": data, "mimeType": f"audio/pcm;rate={INPUT_RATE}"}},
        }))

    async def send_text(self, text: str) -> None:
        """Message tapé au clavier pendant une session Live (réponse vocale)."""
        if not self.active or self._ws is None:
            return
        await self._ws.send(json.dumps({"clientContent": {
            "turns": [{"role": "user", "parts": [{"text": text}]}], "turnComplete": True,
        }}))

    async def stop(self, error: str | None = None) -> None:
        was_active = self.active
        self.active = False
        if self._reader is not None and self._reader is not asyncio.current_task():
            self._reader.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        if was_active or error:
            await self._send("live_state", {"active": False, **({"error": error} if error else {})})

    async def _read_loop(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "serverContent" in msg:
                    await self._on_content(msg["serverContent"])
                if "toolCall" in msg:
                    await self._on_tool_call(msg["toolCall"])
                if "goAway" in msg:
                    logger.info("Gemini Live : fin de session annoncée par le serveur")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Session Gemini Live interrompue: {e}")
            await self.stop(error=str(e)[:200])
            return
        await self.stop()

    async def _on_content(self, content: dict) -> None:
        if content.get("interrupted"):
            await self._send("live_interrupted", {})
        for part in (content.get("modelTurn") or {}).get("parts", []):
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                mime = str(inline.get("mimeType", ""))
                rate = int(mime.split("rate=")[1]) if "rate=" in mime else OUTPUT_RATE
                await self._send("live_audio", {"audio": inline["data"], "rate": rate})
        if (content.get("inputTranscription") or {}).get("text"):
            await self._send("live_transcript", {"role": "user", "text": content["inputTranscription"]["text"]})
        if (content.get("outputTranscription") or {}).get("text"):
            await self._send("live_transcript", {"role": "assistant", "text": content["outputTranscription"]["text"]})
        if content.get("turnComplete"):
            await self._send("live_turn_complete", {})

    async def _on_tool_call(self, call: dict) -> None:
        responses = []
        for fc in call.get("functionCalls", []):
            name = str(fc.get("name", ""))
            args = fc.get("args") or {}
            await self._send("agent_step", {"phase": "tool", "detail": name, "messageId": "live"})
            try:
                result = await self._run_tool(name, args if isinstance(args, dict) else {})
            except Exception as e:
                result = f"Erreur outil {name}: {e}"
            await self._send("tool_result", {"tool": name, "result": str(result)[:300]})
            responses.append({"id": fc.get("id"), "name": name, "response": {"result": str(result)[:8000]}})
        if responses and self._ws is not None:
            await self._ws.send(json.dumps({"toolResponse": {"functionResponses": responses}}))
