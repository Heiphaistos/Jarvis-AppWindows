import asyncio
import json

import api.websocket as wsmod
from core.providers.http import shared_client


class FakeTTS:
    def __init__(self):
        self.active = 0
        self.peak = 0

    async def synthesize(self, text):
        self.active += 1
        self.peak = max(self.peak, self.active)
        # Les phrases courtes finissent d'abord : l'ordre d'envoi doit rester celui du texte.
        await asyncio.sleep(0.05 if len(text) > 10 else 0.01)
        self.active -= 1
        return f"audio:{text}"


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, data):
        self.sent.append(json.loads(data))


async def test_synthese_parallele_et_ordonnee():
    tts, ws, q = FakeTTS(), FakeWS(), asyncio.Queue()
    for s in ["Une phrase plutôt longue.", "Courte.", "Encore une phrase longue."]:
        await q.put(s)
    await q.put(None)
    await wsmod._tts_sentence_worker(q, ws, tts)
    chunks = [e["payload"] for e in ws.sent if e["type"] == "tts_chunk"]
    assert [c["audio"] for c in chunks[:-1]] == ["audio:Une phrase plutôt longue.", "audio:Courte.", "audio:Encore une phrase longue."]
    assert chunks[-1]["final"] is True
    assert tts.peak == 2  # deux synthèses en parallèle, jamais plus


async def test_client_http_partage_par_boucle():
    a = shared_client()
    assert shared_client() is a
    await a.aclose()
    assert shared_client() is not a  # client fermé : recréé
