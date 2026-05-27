from __future__ import annotations
import json
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import get_logger
from core.llm import LLMManager
from core.memory import ContextMemory
from core.stt import STTManager
from core.tts import TTSManager
from tools.registry import ToolRegistry

logger = get_logger("websocket")


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

    async def send(
        self, ws: WebSocket, event_type: str, payload: dict
    ) -> None:
        await ws.send_text(json.dumps({"type": event_type, "payload": payload}))


manager = ConnectionManager()


async def handle_text_query(
    ws: WebSocket,
    text: str,
    llm: LLMManager,
    memory: ContextMemory,
    tts: TTSManager,
) -> None:
    await manager.send(ws, "status", {"status": "processing"})
    memory.add_user(text)
    message_id = str(uuid.uuid4())

    full_response = ""
    async for token in llm.stream(memory.get_messages()):
        full_response += token
        await manager.send(ws, "token", {"token": token, "messageId": message_id})

    memory.add_assistant(full_response)
    await manager.send(ws, "message_done", {"messageId": message_id})

    if full_response.strip() and tts.is_available:
        audio_b64 = await tts.synthesize(full_response)
        if audio_b64:
            await manager.send(ws, "tts_audio", {"audio": audio_b64})
            await manager.send(ws, "status", {"status": "speaking"})
            return

    await manager.send(ws, "status", {"status": "idle"})


async def websocket_handler(
    ws: WebSocket,
    llm: LLMManager,
    memory: ContextMemory,
    stt: STTManager,
    tts: TTSManager,
    tools: ToolRegistry,
) -> None:
    await manager.connect(ws)
    audio_buffer: list[list[float]] = []
    current_sample_rate: int = 16000

    try:
        while True:
            raw = await ws.receive_text()
            event = json.loads(raw)
            event_type: str = event.get("type", "")
            payload: dict = event.get("payload", {})

            if event_type == "text_query":
                await handle_text_query(ws, payload["text"], llm, memory, tts)

            elif event_type == "audio_chunk":
                if stt.is_available:
                    audio_buffer.append(payload["data"])
                    current_sample_rate = payload.get("sampleRate", 16000)
                    if len(audio_buffer) >= 32:
                        text = await stt.transcribe_chunks(
                            audio_buffer, current_sample_rate
                        )
                        audio_buffer.clear()
                        if text.strip():
                            await handle_text_query(ws, text, llm, memory, tts)

            elif event_type == "stop_speaking":
                await manager.send(ws, "status", {"status": "idle"})

            else:
                logger.warning(f"Type d'événement inconnu: {event_type}")

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}", exc_info=True)
        try:
            await manager.send(ws, "error", {"message": str(e)})
        except Exception:
            pass
        manager.disconnect(ws)
