import asyncio

import pytest

import core.persistent_memory as pm
from core import conversation_memory as cm
from core.intent import fast_route
from core.memory import ContextMemory


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "_DB_PATH", tmp_path / "mem.db")
    monkeypatch.setattr(pm, "_instance", None)
    return pm.get_memory()


class FakeProviders:
    def __init__(self, reply="Résumé.", tier="cloud"):
        self.reply, self.tier, self.calls = reply, tier, []

    async def stream(self, system, messages, max_tokens=512, level=None, **kw):
        self.calls.append({"system": system, "content": messages[0]["content"], "level": level})
        yield self.reply


def _chat(ctx: ContextMemory, n: int) -> None:
    for i in range(n):
        ctx.add_user(f"question {i}")
        ctx.add_assistant(f"réponse {i}")


def test_fenetre_garde_les_messages_evacues():
    ctx = ContextMemory(4)
    _chat(ctx, 3)
    assert [m["content"] for m in ctx.get_messages()] == ["question 1", "réponse 1", "question 2", "réponse 2"]
    assert [m["content"] for m in ctx.take_evicted()] == ["question 0", "réponse 0"]
    assert ctx.evicted == [] and ctx.user_turns == 3
    ctx.clear()
    assert ctx.user_turns == 0 and ctx.summary == "" and ctx.episode_id is None


async def test_resume_glissant():
    ctx = ContextMemory(4)
    _chat(ctx, 3)
    ctx.summary = "Monsieur prépare un voyage à Tokyo."
    providers = FakeProviders("Voyage à Tokyo ; question 0 traitée.")
    assert await cm.update_rolling_summary(providers, ctx)
    assert ctx.summary == "Voyage à Tokyo ; question 0 traitée."
    sent = providers.calls[0]
    assert sent["level"] == "instant"
    assert "Monsieur prépare un voyage à Tokyo." in sent["content"]  # ancien résumé intégré
    assert "Monsieur : question 0" in sent["content"]
    assert "Tokyo" in cm.conversation_block(ctx)


async def test_resume_glissant_sans_cerveau_cloud():
    ctx = ContextMemory(2)
    _chat(ctx, 2)
    providers = FakeProviders(tier="local")
    assert not await cm.update_rolling_summary(providers, ctx)
    assert providers.calls == []
    assert len(ctx.evicted) == 2  # rien de perdu : réessayé plus tard


async def test_erreur_du_routeur_n_est_pas_un_resume():
    ctx = ContextMemory(2)
    _chat(ctx, 2)
    assert not await cm.update_rolling_summary(FakeProviders("Tous mes cerveaux sont injoignables, Monsieur."), ctx)
    assert ctx.summary == ""


async def test_episode_cree_puis_mis_a_jour(memory):
    ctx = ContextMemory(20)
    _chat(ctx, 1)
    assert await cm.save_episode(FakeProviders(), ctx, None) is None  # trop court
    _chat(ctx, 2)
    first = await cm.save_episode(FakeProviders("Réglage du HUD."), ctx, None)
    again = await cm.save_episode(FakeProviders("Réglage du HUD puis météo de Lyon."), ctx, first)
    assert first == again
    episodes = memory.episodes()
    assert len(episodes) == 1 and episodes[0]["summary"] == "Réglage du HUD puis météo de Lyon."


def test_recherche_et_prompt_episodes(memory):
    memory.save_episode("Préparation du voyage à Tokyo, réservation de l'hôtel.")
    memory.save_episode("Débogage du serveur FastAPI de JARVIS.")
    memory.save_episode("Recette de la ratatouille.")
    assert [e["summary"][:12] for e in memory.episodes("hôtel tokyo")] == ["Préparation "]
    block = memory.get_episodes_summary("ratatouille", limit=1)
    assert "ratatouille" in block and "CONVERSATIONS PASSÉES" in block


def test_lecons_pertinentes_d_abord(memory):
    memory.record_lesson("météo", "Donner la météo en Celsius.")
    for i in range(10):
        memory.record_lesson(f"divers {i}", f"Leçon sans rapport numéro {i}.")
    block = memory.get_lessons_summary(limit=3, query="quelle météo demain ?")
    assert "Celsius" in block
    assert block.count("\n- ") == 3


def test_outil_recall_conversations(memory):
    from tools.memory_tools import recall_conversations
    assert "Aucune conversation archivée" in recall_conversations()
    memory.save_episode("Choix d'une carte graphique RTX pour le jeu.")
    assert "carte graphique" in recall_conversations("graphique")
    assert "Aucune conversation passée" in recall_conversations("jardinage")


@pytest.mark.parametrize("text", [
    "de quoi on a parlé hier ?",
    "De quoi avons-nous parlé la dernière fois ?",
    "rappelle-moi notre dernière conversation",
])
def test_intention_conversations_passees(text):
    assert fast_route(text) == ("recall_conversations", {"query": ""})


async def test_websocket_archive_et_resume(memory):
    import api.websocket as wsmod

    ctx = ContextMemory(4)
    _chat(ctx, 6)  # 6 messages de Monsieur → archive ; messages évacués → résumé
    providers = FakeProviders("Six questions posées.")
    wsmod._maintain_conversation(providers, ctx)
    await asyncio.gather(*wsmod._learning_tasks)
    assert ctx.summary == "Six questions posées."
    assert ctx.episode_id is not None
    assert memory.episodes()[0]["summary"] == "Six questions posées."
