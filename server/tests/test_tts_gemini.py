import base64
import wave
import io
from pathlib import Path

import httpx
import pytest

from core import tts as tts_mod
from core.tts import TTSManager, pcm_to_wav


class S:
    piper_exe = Path("/nope/piper.exe")
    piper_voice = Path("/nope/voice.onnx")


def test_pcm_to_wav():
    wav = pcm_to_wav(b"\x00\x01" * 2400, rate=24000)
    with wave.open(io.BytesIO(wav)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (24000, 1, 2400)


async def test_gemini_voice_wav(monkeypatch):
    pcm = b"\x10\x00" * 100
    seen = {}

    async def fake_post(self, url, json=None, headers=None, **kw):
        seen["url"], seen["body"], seen["key"] = url, json, headers["x-goog-api-key"]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    t = TTSManager(S())
    t.set_key_provider(lambda: "AIza-test")
    t.set_gemini_voice("Charon")
    assert t.is_available
    audio = await t.synthesize("Bonjour Monsieur.")
    with wave.open(io.BytesIO(base64.b64decode(audio))) as w:
        assert w.getnframes() == 100
    assert seen["key"] == "AIza-test"
    assert seen["body"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Charon"
    assert seen["body"]["contents"][0]["parts"][0]["text"].endswith("Bonjour Monsieur.")


async def test_gemini_sans_cle_bascule(monkeypatch):
    t = TTSManager(S())
    t.set_gemini_voice("Charon")

    async def fake_edge(self, text):
        return "EDGE"

    monkeypatch.setattr(TTSManager, "_synthesize_edge", fake_edge)
    assert await t.synthesize("Bonjour.") == "EDGE"
    # Choisir une voix Edge désactive Gemini
    t.set_edge_voice("fr-FR-RemyMultilingualNeural")
    assert t._gemini_voice is None
