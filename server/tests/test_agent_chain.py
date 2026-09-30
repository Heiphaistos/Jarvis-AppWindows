import asyncio
import json

import api.websocket as wsmod


class WS:
    def __init__(self):
        self.sent = []

    async def send_text(self, data):
        self.sent.append(json.loads(data))


class ScriptedBrain:
    """Cerveau factice : renvoie les réponses prévues, une par appel."""

    def __init__(self, replies, tier="cloud"):
        self.replies = list(replies)
        self.tier = tier
        self.prompts = []

    async def stream(self, system, messages, **kw):
        self.prompts.append(messages[-1]["content"])
        yield self.replies.pop(0) if self.replies else "OK"


class Tools:
    def __init__(self):
        self.calls = []

    def schemas(self):
        return None

    def execute(self, name, **args):
        self.calls.append((name, args))
        return {"get_weather": "Pluie, 12°C", "set_reminder": "✓ Rappel créé"}.get(name, "fait")


def _tag(name, args):
    return f'<JARVIS_TOOL>{{"name": "{name}", "args": {json.dumps(args)}}}</JARVIS_TOOL>'


async def _run(brain, tools):
    return await wsmod._agent_loop(
        ws=WS(), providers=brain, tts=None, tools=tools,
        messages=[{"role": "user", "content": "Météo à Lyon, et s'il pleut rappelle-moi de prendre un parapluie à 8h"}],
        tts_enabled=False, message_id="m", tts_queue=asyncio.Queue(), system="sys",
    )


async def test_enchaine_deux_outils():
    brain = ScriptedBrain([
        _tag("get_weather", {"city": "Lyon"}),
        _tag("set_reminder", {"when": "08:00", "message": "parapluie"}),
        "Il pleut à Lyon, Monsieur : rappel parapluie posé pour 8 h.",
        "OK",  # passe de vérification
    ])
    tools = Tools()
    answer = await _run(brain, tools)
    assert [c[0] for c in tools.calls] == ["get_weather", "set_reminder"]
    assert answer.startswith("Il pleut à Lyon")
    assert "émets maintenant la balise JARVIS_TOOL de l'outil suivant" in brain.prompts[1]


async def test_appel_repete_non_reexecute():
    brain = ScriptedBrain([
        _tag("set_reminder", {"when": "08:00", "message": "parapluie"}),
        _tag("set_reminder", {"message": "parapluie", "when": "08:00"}),  # même appel, autre ordre
        "Rappel posé, Monsieur.",
        "OK",
    ])
    tools = Tools()
    answer = await _run(brain, tools)
    assert tools.calls == [("set_reminder", {"when": "08:00", "message": "parapluie"})]
    assert answer == "Rappel posé, Monsieur."
    # Après la répétition, plus d'enchaînement autorisé : réponse forcée.
    assert "N'émets PAS de balise" in brain.prompts[2]


async def test_pas_d_enchainement_en_local():
    brain = ScriptedBrain([_tag("get_weather", {"city": "Lyon"}), "Il pleut."], tier="local")
    tools = Tools()
    await _run(brain, tools)
    assert "N'émets PAS de balise" in brain.prompts[1]


async def test_dernier_tour_force_la_reponse():
    # Un cerveau qui voudrait appeler des outils à l'infini finit par répondre.
    brain = ScriptedBrain([_tag("get_weather", {"city": f"V{i}"}) for i in range(10)])
    tools = Tools()
    await _run(brain, tools)
    assert len(tools.calls) <= wsmod.MAX_AGENT_ITERATIONS
    assert "N'émets PAS de balise" in brain.prompts[wsmod.MAX_AGENT_ITERATIONS - 1]
