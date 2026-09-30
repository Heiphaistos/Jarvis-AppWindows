import asyncio

import numpy as np

from core.live import LiveSession, gemini_function_declarations, to_pcm16
from tests.fake_live import FakeLive


def test_reechantillonnage_48k_vers_16k():
    pcm = to_pcm16(np.zeros(4800, dtype=np.float32), 48000)
    assert len(pcm) == 1600 * 2
    assert to_pcm16([1.5, -2.0], 16000) == np.array([32767, -32767], dtype="<i2").tobytes()


def test_declarations_gemini():
    decls = gemini_function_declarations([
        {"name": "get_weather", "description": "Météo", "parameters": {
            "type": "object", "properties": {"city": {"type": "string"}, "days": {"type": "integer", "default": 1}},
            "required": ["city"]}},
        {"name": "get_datetime", "description": "Heure", "parameters": {"type": "object", "properties": {}, "required": []}},
    ])
    assert decls[0]["parameters"] == {"type": "OBJECT", "properties": {
        "city": {"type": "STRING"}, "days": {"type": "INTEGER"}}, "required": ["city"]}
    assert "parameters" not in decls[1]


async def test_session_complete():
    events = []

    async def send(t, data):
        events.append((t, data))

    async def run_tool(name, args):
        return "Nous sommes jeudi, il est 12h00."

    async with FakeLive() as fake:
        live = LiveSession("KEY", send, run_tool, system="Tu es JARVIS.", voice="Orus", url=fake.url,
                           tools=[{"name": "get_datetime", "description": "Heure", "parameters": {"type": "object", "properties": {}, "required": []}}])
        await live.start()
        await live.send_audio([0.1] * 4800, 48000)
        for _ in range(100):
            if any(t == "live_turn_complete" for t, _ in events):
                break
            await asyncio.sleep(0.02)
        await live.send_text("merci")
        await asyncio.sleep(0.2)
        await live.stop()

    types = [t for t, _ in events]
    assert types[0] == "live_state" and events[0][1]["active"] is True
    assert fake.setup["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Orus"
    assert fake.setup["tools"][0]["functionDeclarations"][0]["name"] == "get_datetime"
    assert fake.audio_bytes == 1600 * 2  # 4800 éch. à 48 kHz → 1600 à 16 kHz
    assert ("live_transcript", {"role": "user", "text": "quelle heure est-il"}) in events
    assert fake.tool_responses[0]["functionResponses"][0] == {
        "id": "c1", "name": "get_datetime", "response": {"result": "Nous sommes jeudi, il est 12h00."}}
    assert any(t == "live_audio" and d["rate"] == 24000 for t, d in events)
    assert ("live_transcript", {"role": "assistant", "text": "Il est midi, Monsieur."}) in events
    assert "live_interrupted" in types
    assert events[-1] == ("live_state", {"active": False})


async def test_refus_de_setup():
    import json
    import websockets

    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"error": {"message": "modèle inconnu"}}))

    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    live = LiveSession("KEY", lambda *a: asyncio.sleep(0), lambda *a: asyncio.sleep(0), "", url=f"ws://127.0.0.1:{port}")
    try:
        await live.start()
        raise AssertionError("aurait dû échouer")
    except RuntimeError as e:
        assert "refusé" in str(e)
    finally:
        server.close()
