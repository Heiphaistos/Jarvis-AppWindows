import asyncio
import json

import pytest

import core.persistent_memory as pm
from core import auto_memory as am


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "_DB_PATH", tmp_path / "mem.db")
    monkeypatch.setattr(pm, "_instance", None)
    monkeypatch.delenv("JARVIS_AUTO_MEMORY", raising=False)
    return pm.get_memory()


class FakeProviders:
    """Cerveau factice : renvoie un JSON d'extraction préparé, mémorise le prompt reçu."""

    def __init__(self, reply: str, tier: str = "cloud"):
        self.reply = reply
        self.tier = tier
        self.calls = []

    async def stream(self, system, messages, max_tokens=512, level=None, **kw):
        self.calls.append({"system": system, "messages": messages, "level": level})
        for i in range(0, len(self.reply), 7):
            yield self.reply[i:i + 7]


def _reply(facts=(), forget=(), lesson=""):
    return json.dumps({"facts": list(facts), "forget": list(forget), "lesson": lesson}, ensure_ascii=False)


# ── Filtres ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Je m'appelle Mohamed et j'habite à Lyon",
    "J'adore le jazz et la cuisine japonaise",
    "Mon projet en ce moment c'est une appli de fitness",
    "Non, c'est faux, la capitale de l'Australie c'est Canberra",
    "À l'avenir réponds-moi toujours en deux phrases",
    "Oublie ma ville",
])
def test_messages_personnels_detectes(text):
    assert am.worth_extracting(text)


@pytest.mark.parametrize("text", [
    "ouvre mon navigateur",
    "quelle heure est-il ?",
    "salut",
    "calcule 17*23",
    "mets ma musique",
])
def test_commandes_et_questions_ignorees(text):
    assert not am.worth_extracting(text)


def test_regles_locales():
    facts = {f.key: f for f in am.extract_with_rules(
        "Salut, je m'appelle Mohamed, j'ai 27 ans, j'habite à Aix-en-Provence depuis 2020 "
        "et je travaille comme développeur web chez Capgemini."
    )}
    assert facts["prenom"].value == "Mohamed"
    assert facts["age"].value == "27"
    assert facts["ville"].value == "Aix-en-Provence"
    assert facts["metier"].value == "développeur web"
    assert facts["employeur"].value == "Capgemini"
    assert facts["prenom"].category == "identite"


def test_normalisation_des_cles():
    assert am.normalize_key("Ville d'habitation") == "ville_d_habitation"
    assert am.normalize_key("  Prénom épouse ") == "prenom_epouse"


def test_parse_tolere_le_bruit_et_filtre():
    raw = "Voici :\n```json\n" + _reply(
        facts=[
            {"key": "Langage préféré", "value": "Python", "category": "preferences"},
            {"key": "mot_de_passe_wifi", "value": "hunter2", "category": "general"},
            {"key": "carte", "value": "4970 1012 3456 7890", "category": "general"},
            {"key": "x", "value": "trop court", "category": "general"},
            {"key": "sport", "value": "Escalade", "category": "inconnue"},
        ],
        forget=["Ancienne Ville"],
        lesson="Donner les températures en Celsius.",
    ) + "\n```"
    learned = am.parse_extraction(raw)
    keys = {f.key: f for f in learned.saved}
    assert set(keys) == {"langage_prefere", "sport"}
    assert keys["sport"].category == "general"  # catégorie inconnue → general
    assert learned.forgotten == ["ancienne_ville"]
    assert learned.lesson == "Donner les températures en Celsius."


def test_parse_json_invalide():
    assert not am.parse_extraction("je ne sais pas")
    assert not am.parse_extraction("{pas du json}")


# ── Bout en bout ─────────────────────────────────────────────────────────────

async def test_apprend_faits_et_met_a_jour(memory):
    memory.save("ville", "Paris", "lieux")
    providers = FakeProviders(_reply(facts=[
        {"key": "ville", "value": "Lyon", "category": "lieux"},
        {"key": "musique_preferee", "value": "le jazz", "category": "preferences"},
    ]))
    learned = await am.learn_from_exchange(
        providers, "J'ai déménagé, maintenant j'habite à Lyon. J'adore le jazz.", "Noté, Monsieur.",
    )
    facts = {f["key"]: f["value"] for f in memory.facts()}
    assert facts["ville"] == "Lyon"  # mis à jour, pas dupliqué
    assert facts["musique_preferee"] == "le jazz"
    assert memory.count() == 2
    assert {f.key for f in learned.saved} == {"ville", "musique_preferee"}
    # Le cerveau rapide est utilisé et voit les souvenirs existants.
    assert providers.calls[0]["level"] == "instant"
    assert "ville (lieux)" in providers.calls[0]["messages"][0]["content"]


async def test_correction_donne_une_lecon(memory):
    providers = FakeProviders(_reply(lesson="Donner les distances en kilomètres, jamais en miles."))
    learned = await am.learn_from_exchange(
        providers, "Non, je t'ai dit de parler en kilomètres, pas en miles !",
        "Pardon Monsieur, cela fait 12 km.", previous_assistant="C'est à environ 7 miles.",
    )
    assert learned.lesson.startswith("Donner les distances")
    assert "kilomètres" in memory.get_lessons_summary()
    assert "7 miles" in providers.calls[0]["messages"][0]["content"]


async def test_oubli(memory):
    memory.save("ville", "Lyon", "lieux")
    providers = FakeProviders(_reply(forget=["ville"]))
    learned = await am.learn_from_exchange(providers, "Oublie où j'habite, s'il te plaît.", "C'est oublié.")
    assert learned.forgotten == ["ville"]
    assert memory.count() == 0


async def test_cerveau_local_regles_seulement(memory):
    providers = FakeProviders(_reply(facts=[{"key": "z", "value": "ne doit pas passer", "category": "general"}]), tier="local")
    await am.learn_from_exchange(providers, "Je m'appelle Tony et j'habite à Malibu.", "Enchanté.")
    assert providers.calls == []  # jamais le 7B local : il bloquerait la question suivante
    assert {f["key"]: f["value"] for f in memory.facts()} == {"prenom": "Tony", "ville": "Malibu"}


async def test_rien_pour_une_commande(memory):
    providers = FakeProviders(_reply(facts=[{"key": "a", "value": "b", "category": "general"}]))
    learned = await am.learn_from_exchange(providers, "quelle heure est-il ?", "Il est 10 h.")
    assert not learned and providers.calls == [] and memory.count() == 0


async def test_desactivable(memory, monkeypatch):
    providers = FakeProviders(_reply(facts=[{"key": "sport", "value": "boxe", "category": "habitudes"}]))
    am.set_enabled(False)
    assert not am.is_enabled()
    await am.learn_from_exchange(providers, "Je fais de la boxe tous les mardis.", "Bien noté.")
    assert memory.count() == 0
    am.set_enabled(True)
    monkeypatch.setenv("JARVIS_AUTO_MEMORY", "0")
    assert not am.is_enabled()


async def test_cerveau_en_panne_ne_casse_rien(memory):
    class Broken(FakeProviders):
        async def stream(self, *a, **kw):
            raise RuntimeError("503")
            yield ""  # pragma: no cover

    learned = await am.learn_from_exchange(Broken(""), "Je m'appelle Pepper.", "Enchanté.")
    assert [f.key for f in learned.saved] == ["prenom"]  # les règles locales ont suffi


def test_contexte_pertinent_dans_le_prompt(memory):
    for i in range(40):
        memory.save(f"divers_{i}", f"détail sans rapport {i}", "general")
    memory.save("prenom", "Tony", "identite")
    memory.save("voiture", "Audi R8 rouge", "general")
    ctx = memory.get_context_summary("parle-moi de ma voiture", limit=5)
    assert "prenom: Tony" in ctx  # l'identité passe toujours
    assert "voiture: Audi R8 rouge" in ctx  # pertinent pour la demande
    assert ctx.count("\n- ") == 5


async def test_websocket_apprend_en_arriere_plan(memory, monkeypatch):
    import api.websocket as wsmod

    sent = []

    class WS:
        async def send_text(self, data):
            sent.append(json.loads(data))

    providers = FakeProviders(_reply(facts=[{"key": "equipe", "value": "OM", "category": "preferences"}]))
    wsmod._learn_in_background(WS(), providers, "Je supporte l'OM depuis tout petit.", "Allez l'OM !", "")
    await asyncio.gather(*wsmod._learning_tasks)
    update = next(e["payload"] for e in sent if e["type"] == "memory_update")
    assert update["saved"] == [{"key": "equipe", "value": "OM", "category": "preferences"}]
    assert "equipe = OM" in update["summary"]
