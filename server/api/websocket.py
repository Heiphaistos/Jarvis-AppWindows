from __future__ import annotations
import asyncio
import json
import re
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import get_logger
from utils.config import MODELS_DIR
from core.llm import LLMManager, parse_tool_call, _TOOL_CALL_RE
from core.memory import ContextMemory
from core.stt import STTManager
from core.tts import TTSManager
from tools.registry import ToolRegistry

from utils.rate_limiter import RateLimiter

_rate_limiter = RateLimiter()

logger = get_logger("websocket")

CHUNK_THRESHOLD = 8
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024   # 2 MB — audio chunk upper bound
MAX_TEXT_CHARS = 2000
ALLOWED_ORIGINS = {
    "http://localhost:1420",    # dev Vite
    "http://127.0.0.1:1420",    # dev Vite alt
    "tauri://localhost",         # Tauri v1 production
    "http://tauri.localhost",    # Tauri v2 production (WebView2)
    "https://tauri.localhost",   # Tauri v2 HTTPS variant
}

_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?…»!?"])\s+|(?<=\.\.\.)\s+')

MAX_AGENT_ITERATIONS = 5


async def _agent_loop(
    ws: "WebSocket",
    llm: "LLMManager",
    tts: "TTSManager",
    tools: "ToolRegistry",
    messages: list[dict],
    tts_enabled: bool,
    message_id: str,
    tts_queue: "asyncio.Queue[str]",
) -> str:
    """Boucle agent : LLM → tool → LLM → ... → réponse finale (max 5 itérations)."""
    accumulated = ""

    for _iteration in range(MAX_AGENT_ITERATIONS):
        full_response = ""
        sentence_buf = ""
        in_tool_tag = False

        async for token in llm.stream(messages):
            full_response += token
            # Détecter début de balise tool → bufferiser sans envoyer
            if "<JARVIS_TOOL>" in full_response and "</JARVIS_TOOL>" not in full_response:
                in_tool_tag = True
            if in_tool_tag:
                if "</JARVIS_TOOL>" in full_response:
                    in_tool_tag = False
                    # Balise complète → on arrête le streaming ici
                    break
                continue  # Bufferiser, pas encore au client

            # Token normal → envoyer au client
            await manager.send(ws, "token", {"token": token, "messageId": message_id})
            accumulated += token

            # Buffer TTS phrase par phrase
            if tts_enabled:
                sentence_buf += token
                m = _SENTENCE_BOUNDARY.search(sentence_buf)
                if m and len(sentence_buf.strip()) > 15:
                    phrase = sentence_buf[: m.start() + 1].strip()
                    sentence_buf = sentence_buf[m.end():]
                    if phrase:
                        await tts_queue.put(phrase)

        # Vérifier si tool call présent dans la réponse complète
        tool_result = parse_tool_call(full_response)
        if tool_result:
            name, args = tool_result
            logger.info(f"Agent loop iteration {_iteration + 1}: tool call {name}({args})")
            # Notifier le client (outil en cours)
            await manager.send(ws, "tool_result", {"tool": name, "result": f"⚙️ Exécution de {name}..."})
            # Exécuter l'outil dans un thread (opération bloquante possible)
            try:
                result = await asyncio.to_thread(tools.execute, name, **args)
            except Exception as e:
                result = f"Erreur outil {name}: {e}"
                logger.error(f"Tool execution error: {e}", exc_info=True)

            # Envoyer le résultat au client
            await manager.send(ws, "tool_result", {"tool": name, "result": str(result)[:300]})

            # Extraire le texte visible avant la balise tool (s'il y en a)
            visible = _TOOL_CALL_RE.sub("", full_response).strip()
            if visible and visible not in accumulated:
                await manager.send(ws, "token", {"token": visible, "messageId": message_id})
                accumulated += visible

            # Réinjecter dans le contexte pour la prochaine itération LLM
            messages = messages + [
                {"role": "assistant", "content": full_response},
                {
                    "role": "user",
                    "content": (
                        f"[RÉSULTAT OUTIL {name}]\n{result}\n\n"
                        "Continue ta réponse en français en tenant compte de ce résultat. "
                        "Ne répète pas ce que tu viens de faire."
                    ),
                },
            ]
            continue  # Prochaine itération

        else:
            # Pas de tool → réponse finale
            # Envoyer ce qui n'a pas encore été streamé
            remaining = _TOOL_CALL_RE.sub("", full_response).strip()
            if remaining and remaining not in accumulated:
                await manager.send(ws, "token", {"token": remaining, "messageId": message_id})
                accumulated += remaining

            # Flush le dernier buffer TTS
            if tts_enabled and sentence_buf.strip():
                await tts_queue.put(sentence_buf.strip())

            break  # Réponse finale → sortir de la boucle

    return accumulated


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


async def _tts_sentence_worker(
    queue: asyncio.Queue[str | None],
    ws: WebSocket,
    tts: TTSManager,
) -> None:
    """Consomme les phrases de la queue, synthétise et envoie les chunks audio.

    Garantit l'envoi du chunk final même si une synthèse échoue.
    """
    index = 0
    try:
        while True:
            sentence: str | None = await queue.get()
            if sentence is None:
                break
            try:
                audio_b64 = await tts.synthesize(sentence)
                if audio_b64:
                    await manager.send(ws, "tts_chunk", {"audio": audio_b64, "final": False, "index": index})
                    index += 1
            except Exception as e:
                logger.warning(f"TTS synthesis failed for sentence: {e}")
    finally:
        await manager.send(ws, "tts_chunk", {"audio": "", "final": True, "index": index})


async def _stream_llm_with_tts(
    ws: WebSocket,
    llm: LLMManager,
    memory: ContextMemory,
    tts: TTSManager,
    tts_enabled: bool,
    message_id: str,
    max_tokens: int = 256,
) -> str:
    """Stream LLM tokens vers le client et lance TTS concurrent par phrase.

    Retourne la réponse complète. Garantit le nettoyage du tts_task même en cas
    d'exception via try/finally.
    """
    tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
    tts_task = None
    if tts_enabled and tts.is_available:
        tts_task = asyncio.create_task(_tts_sentence_worker(tts_queue, ws, tts))

    full_response = ""
    sentence_buf = ""

    try:
        async for token in llm.stream(memory.get_messages(), max_tokens=max_tokens):
            full_response += token
            if "<JARVIS_TOOL>" not in full_response:
                await manager.send(ws, "token", {"token": token, "messageId": message_id})

            if tts_task and "<JARVIS_TOOL>" not in full_response:
                sentence_buf += token
                m = _SENTENCE_BOUNDARY.search(sentence_buf)
                if m:
                    phrase = sentence_buf[: m.start() + 1].strip()
                    sentence_buf = sentence_buf[m.end():]
                    if phrase:
                        await tts_queue.put(phrase)
    finally:
        if tts_task:
            # Flush le buffer restant puis signal de fin — garanti même si exception
            if sentence_buf.strip() and "<JARVIS_TOOL>" not in sentence_buf:
                await tts_queue.put(sentence_buf.strip())
            await tts_queue.put(None)
            await tts_task

    return full_response


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

    # ── Agent loop (multi-tool, max MAX_AGENT_ITERATIONS) ──────────────────
    tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
    tts_task = None
    if tts_enabled and tts.is_available:
        tts_task = asyncio.create_task(_tts_sentence_worker(tts_queue, ws, tts))

    try:
        final_text = await _agent_loop(
            ws=ws,
            llm=llm,
            tts=tts,
            tools=tools,
            messages=memory.get_messages(),
            tts_enabled=tts_enabled and tts.is_available,
            message_id=message_id,
            tts_queue=tts_queue,
        )
    finally:
        if tts_task:
            await tts_queue.put(None)
            await tts_task

    if final_text:
        memory.add_assistant(final_text)

    await manager.send(ws, "message_done", {"messageId": message_id})
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
    ws_id = id(ws)

    from core.monitor import subscribe as _monitor_subscribe, unsubscribe as _monitor_unsubscribe
    alert_queue = _monitor_subscribe()

    async def _forward_alerts():
        while True:
            try:
                alert = await asyncio.wait_for(alert_queue.get(), timeout=1.0)
                await manager.send(ws, alert["type"], alert["payload"])
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    alert_task = asyncio.create_task(_forward_alerts())

    # Notify client of server capabilities immediately on connect
    await manager.send(ws, "server_status", {
        "llm": llm.is_available,
        "stt": stt.is_available,
        "tts": tts.is_available,
    })

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
                if not _rate_limiter.allow_text(ws_id):
                    await manager.send(ws, "error", {"message": "Trop de requêtes. Patientez une minute."})
                    continue
                text = str(payload.get("text", "")).strip()
                if not text:
                    continue
                text = text[:MAX_TEXT_CHARS]
                await handle_text_query(ws, text, llm, memory, tts, tools, tts_enabled)

            elif event_type == "audio_chunk":
                if not _rate_limiter.allow_audio(ws_id):
                    continue
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
        pass
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}", exc_info=True)
        audio_buffer.clear()
        try:
            await manager.send(ws, "error", {"message": "Erreur interne du serveur."})
        except Exception:
            pass
    finally:
        alert_task.cancel()
        _monitor_unsubscribe(alert_queue)
        _rate_limiter.cleanup(ws_id)
        manager.disconnect(ws)
