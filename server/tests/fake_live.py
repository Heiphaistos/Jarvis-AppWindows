"""Faux serveur Gemini Live (protocole BidiGenerateContent) pour les tests."""
import asyncio
import base64
import json

import websockets

PCM = base64.b64encode(b"\x01\x00" * 480).decode()


class FakeLive:
    def __init__(self):
        self.setup = None
        self.audio_bytes = 0
        self.tool_responses = []
        self.url = ""
        self._server = None

    async def __aenter__(self):
        self._server = await websockets.serve(self._handler, "127.0.0.1", 0)
        port = self._server.sockets[0].getsockname()[1]
        self.url = f"ws://127.0.0.1:{port}/live"
        return self

    async def __aexit__(self, *exc):
        self._server.close()
        await self._server.wait_closed()

    async def _handler(self, ws):
        self.setup = json.loads(await ws.recv())["setup"]
        await ws.send(json.dumps({"setupComplete": {}}))
        asked = False
        async for raw in ws:
            msg = json.loads(raw)
            if "realtimeInput" in msg:
                self.audio_bytes += len(base64.b64decode(msg["realtimeInput"]["audio"]["data"]))
                if not asked:
                    asked = True
                    await ws.send(json.dumps({"serverContent": {"inputTranscription": {"text": "quelle heure est-il"}}}))
                    await ws.send(json.dumps({"toolCall": {"functionCalls": [{"id": "c1", "name": "get_datetime", "args": {}}]}}))
            elif "toolResponse" in msg:
                self.tool_responses.append(msg["toolResponse"])
                await ws.send(json.dumps({"serverContent": {"modelTurn": {"parts": [
                    {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": PCM}}]}}}))
                await ws.send(json.dumps({"serverContent": {"outputTranscription": {"text": "Il est midi, Monsieur."}}}))
                await ws.send(json.dumps({"serverContent": {"turnComplete": True}}))
            elif "clientContent" in msg:
                await ws.send(json.dumps({"serverContent": {"interrupted": True}}))
                await ws.send(json.dumps({"serverContent": {"outputTranscription": {"text": "Bien reçu."}, "turnComplete": True}}))
