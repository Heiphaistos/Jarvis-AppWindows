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

# Transcription every ~2s of audio (8 chunks × 4096 samples @ 16kHz ≈ 2.05s)
CHUNK_THRESHOLD = 8


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
    tts_enabled: bool = True,
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

    # TTS : synthèse vocale + envoi audio
    if tts_enabled and full_response.strip() and tts.is_available:
        await manager.send(ws, "status", {"status": "speaking"})
        audio_b64 = await tts.synthesize(full_response)
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
    tts_enabled: bool = True,
) -> None:
    if not audio_buffer:
        return
    text = await stt.transcribe_chunks(audio_buffer, sample_rate)
    logger.info(f"STT transcription: '{text}'")
    if text.strip():
        await manager.send(ws, "stt_text", {"text": text.strip()})
        await handle_text_query(ws, text.strip(), llm, memory, tts, tts_enabled)


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
    tts_enabled: bool = True

    try:
        while True:
            raw = await ws.receive_text()
            event = json.loads(raw)
            event_type: str = event.get("type", "")
            payload: dict = event.get("payload", {})

            if event_type == "text_query":
                await handle_text_query(ws, payload["text"], llm, memory, tts, tts_enabled)

            elif event_type == "audio_chunk":
                if stt.is_available:
                    audio_buffer.append(payload["data"])
                    current_sample_rate = payload.get("sampleRate", 16000)
                    # Send listening feedback on first chunk
                    if len(audio_buffer) == 1:
                        await manager.send(ws, "status", {"status": "listening"})
                    # Transcribe every CHUNK_THRESHOLD chunks (≈ 2s)
                    if len(audio_buffer) >= CHUNK_THRESHOLD:
                        chunks = list(audio_buffer)
                        audio_buffer.clear()
                        await transcribe_and_query(
                            ws, chunks, current_sample_rate, stt, llm, memory, tts, tts_enabled
                        )
                        if stt.is_available:
                            await manager.send(ws, "status", {"status": "listening"})

            elif event_type == "mic_stop":
                if audio_buffer and stt.is_available:
                    chunks = list(audio_buffer)
                    audio_buffer.clear()
                    await transcribe_and_query(
                        ws, chunks, current_sample_rate, stt, llm, memory, tts, tts_enabled
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
                voice_id = payload.get("voice", "")
                if voice_id:
                    from pathlib import Path
                    from utils.config import MODELS_DIR
                    voice_path = MODELS_DIR / "piper" / f"{voice_id}.onnx"
                    if voice_path.exists():
                        tts._voice = voice_path
                        tts._available = tts._piper_exe.exists() and voice_path.exists()
                        logger.info(f"Voix changée: {voice_id}")
                    else:
                        logger.warning(f"Voix introuvable: {voice_path}")

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
