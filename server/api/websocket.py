from __future__ import annotations
import json
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import get_logger
from utils.config import MODELS_DIR
from core.llm import LLMManager, parse_tool_call
from core.memory import ContextMemory
from core.stt import STTManager
from core.tts import TTSManager
from tools.registry import ToolRegistry

logger = get_logger("websocket")

CHUNK_THRESHOLD = 8
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024   # 2 MB — audio chunk upper bound
MAX_TEXT_CHARS = 2000
ALLOWED_ORIGINS = {"http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"}


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("Client WebSocket connecté")

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)
        logger.info("Client WebSocket déconnecté")

    async def send(self, ws: WebSocket, event_type: str, payload: dict) -> None:
        await ws.send_text(json.dumps({"type": event_type, "payload": payload}))


manager = ConnectionManager()


async def handle_text_query(
    ws: WebSocket,
    text: str,
    llm: LLMManager,
    memory: ContextMemory,
    tts: TTSManager,
    tools: ToolRegistry,
    tts_enabled: bool = True,
) -> None:
    await manager.send(ws, "status", {"status": "processing"})
    memory.add_user(text)
    message_id = str(uuid.uuid4())

    full_response = ""
    async for token in llm.stream(memory.get_messages()):
        full_response += token
        # Don't stream the internal tool-call marker to the client
        if "<JARVIS_TOOL>" not in full_response:
            await manager.send(ws, "token", {"token": token, "messageId": message_id})

    # Handle tool call if present
    tool_call = parse_tool_call(full_response)
    if tool_call:
        tool_name, tool_args = tool_call
        logger.info(f"Tool call: {tool_name}({tool_args})")
        tool_result = tools.execute(tool_name, **tool_args)

        # Inject tool result and ask LLM for a natural response
        tool_context = f"[Résultat de {tool_name}: {tool_result}]"
        memory.add_assistant(tool_context)

        # Second LLM pass — send result to client as continuation
        second_id = str(uuid.uuid4())
        second_response = ""
        async for token in llm.stream(memory.get_messages(), max_tokens=256):
            second_response += token
            await manager.send(ws, "token", {"token": token, "messageId": second_id})

        memory.add_assistant(second_response)
        await manager.send(ws, "message_done", {"messageId": second_id})
    else:
        memory.add_assistant(full_response)
        await manager.send(ws, "message_done", {"messageId": message_id})

    if tts_enabled and (tool_call or full_response.strip()) and tts.is_available:
        tts_text = full_response if not tool_call else second_response  # type: ignore[possibly-undefined]
        if tts_text.strip():
            await manager.send(ws, "status", {"status": "speaking"})
            audio_b64 = await tts.synthesize(tts_text)
            if audio_b64:
                await manager.send(ws, "tts_audio", {"audio": audio_b64})
                return

    await manager.send(ws, "status", {"status": "idle"})


async def transcribe_and_query(
    ws: WebSocket,
    audio_buffer: list[list[float]],
    sample_rate: int,
    stt: STTManager,
    llm: LLMManager,
    memory: ContextMemory,
    tts: TTSManager,
    tools: ToolRegistry,
    tts_enabled: bool = True,
) -> None:
    if not audio_buffer:
        return
    text = await stt.transcribe_chunks(audio_buffer, sample_rate)
    logger.info(f"STT transcription: '{text}'")
    if text.strip():
        await manager.send(ws, "stt_text", {"text": text.strip()})
        await handle_text_query(ws, text.strip(), llm, memory, tts, tools, tts_enabled)


async def websocket_handler(
    ws: WebSocket,
    llm: LLMManager,
    stt: STTManager,
    tts: TTSManager,
    tools: ToolRegistry,
    max_context_messages: int = 20,
) -> None:
    # Origin check — reject connections from unexpected origins
    origin = ws.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        logger.warning(f"Origine WebSocket refusée: {origin!r}")
        await ws.close(code=4403, reason="Origin not allowed")
        return

    await manager.connect(ws)

    # Per-connection memory — no shared state between clients
    memory = ContextMemory(max_context_messages)

    audio_buffer: list[list[float]] = []
    current_sample_rate: int = 16000
    tts_enabled: bool = True

    try:
        while True:
            raw = await ws.receive_text()

            if len(raw) > MAX_PAYLOAD_BYTES:
                logger.warning(f"Payload trop grand: {len(raw)} bytes")
                continue

            event = json.loads(raw)
            event_type: str = event.get("type", "")
            payload: dict = event.get("payload", {})

            if event_type == "text_query":
                text = str(payload.get("text", "")).strip()
                if not text:
                    continue
                text = text[:MAX_TEXT_CHARS]
                await handle_text_query(ws, text, llm, memory, tts, tools, tts_enabled)

            elif event_type == "audio_chunk":
                if stt.is_available:
                    chunk_data = payload.get("data")
                    if not isinstance(chunk_data, list):
                        continue
                    audio_buffer.append(chunk_data)
                    current_sample_rate = int(payload.get("sampleRate", 16000))
                    if len(audio_buffer) == 1:
                        await manager.send(ws, "status", {"status": "listening"})
                    if len(audio_buffer) >= CHUNK_THRESHOLD:
                        chunks = list(audio_buffer)
                        audio_buffer.clear()
                        await transcribe_and_query(
                            ws, chunks, current_sample_rate, stt, llm, memory, tts, tools, tts_enabled
                        )
                        if stt.is_available:
                            await manager.send(ws, "status", {"status": "listening"})

            elif event_type == "mic_stop":
                if audio_buffer and stt.is_available:
                    chunks = list(audio_buffer)
                    audio_buffer.clear()
                    await transcribe_and_query(
                        ws, chunks, current_sample_rate, stt, llm, memory, tts, tools, tts_enabled
                    )
                else:
                    audio_buffer.clear()
                    await manager.send(ws, "status", {"status": "idle"})

            elif event_type == "tts_done":
                await manager.send(ws, "status", {"status": "idle"})

            elif event_type == "set_tts":
                tts_enabled = bool(payload.get("enabled", True))
                logger.info(f"TTS {'activé' if tts_enabled else 'désactivé'}")

            elif event_type == "set_voice":
                voice_id = str(payload.get("voice", "")).strip()
                if voice_id:
                    from pathlib import Path
                    voice_path = MODELS_DIR / "piper" / f"{voice_id}.onnx"
                    if voice_path.exists():
                        tts.set_voice(voice_path)
                    else:
                        logger.warning(f"Voix introuvable: {voice_path}")

            elif event_type == "clear_history":
                memory.clear()
                logger.info("Historique effacé")

            else:
                logger.warning(f"Type d'événement inconnu: {event_type}")

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}", exc_info=True)
        audio_buffer.clear()
        try:
            await manager.send(ws, "error", {"message": "Erreur interne du serveur."})
        except Exception:
            pass
        manager.disconnect(ws)
