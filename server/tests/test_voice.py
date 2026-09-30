import numpy as np
import pytest

import api.websocket as wsmod
from core import cloud_stt
from core.stt import STTManager, clean_transcript, is_hallucination


@pytest.mark.parametrize("text", [
    "Sous-titres réalisés par la communauté d'Amara.org",
    "Merci d'avoir regardé cette vidéo !",
    "Sous-titrage ST' 501",
    "Commandes vocales en français adressées à JARVIS, assistant personnel",
    "oui oui oui oui oui oui oui",
    "...",
])
def test_hallucinations_rejetees(text):
    assert is_hallucination(text)


@pytest.mark.parametrize("text", [
    "Ouvre google.com",
    "Traduction de hello en espagnol",
    "Lance la transcription de ma réunion",
    "À bientôt Jarvis",
    "Merci",
    "Au revoir",
    "Quelle heure est-il ?",
])
def test_vraies_commandes_conservees(text):
    assert not is_hallucination(text)


def test_nom_de_jarvis_retabli():
    assert clean_transcript("Jervis, quelle heure  est-il ?") == "Jarvis, quelle heure est-il ?"
    assert clean_transcript("ok jar vice ouvre chrome") == "ok Jarvis ouvre chrome"


def test_preparation_audio():
    silence = [[0.0001] * 1600] * 5
    assert STTManager.prepare(silence, 16000) is None
    t = np.linspace(0, 1, 48000, dtype=np.float32)
    voice = (0.02 * np.sin(2 * np.pi * 220 * t)).tolist()
    audio = STTManager.prepare([voice], 48000)
    assert audio is not None and len(audio) == 16000  # rééchantillonné 48 → 16 kHz
    assert 0.08 < float(np.sqrt(np.mean(audio ** 2))) < 0.12  # normalisé vers RMS 0,1


def test_wav():
    wav = cloud_stt.to_wav(np.zeros(1600, dtype=np.float32))
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"


class Providers:
    def __init__(self, keys):
        self.keys = keys
        self._configs = {}

    def api_key(self, name):
        return self.keys.get(name, "")


class Resp:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class Http:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    async def post(self, url, **kw):
        self.calls.append((url, kw["data"]["model"], kw["headers"]["Authorization"]))
        return self.replies.pop(0)


async def test_cloud_groq_puis_openai():
    audio = np.zeros(16000, dtype=np.float32)
    http = Http([Resp(429, {}), Resp(200, {"text": " Jervis, ouvre google.com "})])
    text = await cloud_stt.transcribe(audio, Providers({"groq": "gk", "openai": "ok"}), client=http)
    assert text == "Jarvis, ouvre google.com"
    assert [c[1] for c in http.calls] == ["whisper-large-v3-turbo", "gpt-4o-mini-transcribe"]
    assert http.calls[0][0] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert http.calls[0][2] == "Bearer gk"


async def test_cloud_hallucination_et_absence_de_cle(monkeypatch):
    audio = np.zeros(16000, dtype=np.float32)
    http = Http([Resp(200, {"text": "Sous-titres réalisés par Amara.org"})])
    assert await cloud_stt.transcribe(audio, Providers({"groq": "gk"}), client=http) == ""
    assert await cloud_stt.transcribe(audio, Providers({}), client=Http([])) is None
    monkeypatch.setenv("JARVIS_CLOUD_STT", "0")
    assert cloud_stt.engines(Providers({"groq": "gk"})) == []


async def test_repli_sur_whisper_local(monkeypatch):
    class LocalSTT:
        is_available = True

        async def transcribe_audio(self, audio):
            return "quelle heure est-il", True

    async def cloud_down(audio, providers, client=None):
        return None

    monkeypatch.setattr(cloud_stt, "transcribe", cloud_down)
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    voice = (0.05 * np.sin(2 * np.pi * 220 * t)).tolist()
    text, uncertain = await wsmod.transcribe([voice], 16000, LocalSTT(), Providers({}))
    assert text == "quelle heure est-il" and uncertain


def test_voix_disponible_sans_whisper_local():
    class NoLocal:
        is_available = False

    assert not wsmod.voice_available(NoLocal(), Providers({}))
    assert wsmod.voice_available(NoLocal(), Providers({"groq": "gk"}))


def test_consignes_mode_vocal():
    sure = wsmod._voice_block(False)
    assert "MODE VOCAL" in sure and "demandez de répéter" in sure and "INCERTAINE" not in sure
    assert "demandez confirmation" in wsmod._voice_block(True)
