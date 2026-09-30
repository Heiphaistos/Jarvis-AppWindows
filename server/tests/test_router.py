import asyncio

import pytest

from core.providers.base import LLMProvider, ProviderError
from core.providers.manager import ProviderManager
from core.providers.router import Telemetry, brain_key, classify, hedged_stream, order_candidates


class FakeBrain(LLMProvider):
    tier = "cloud"

    def __init__(self, name, delay=0.0, tokens=("ok",), fail=False, fail_after=None):
        self.name = name
        self.label = name.upper()
        self._delay = delay
        self._tokens = tokens
        self._fail = fail
        self._fail_after = fail_after
        self.calls = 0
        self.cancelled = False

    @property
    def is_available(self):
        return True

    @property
    def model(self):
        return f"{self.name}-model"

    async def stream(self, system, messages, max_tokens=512):
        self.calls += 1
        try:
            await asyncio.sleep(self._delay)
            if self._fail:
                raise ProviderError(f"{self.name} en panne")
            for i, t in enumerate(self._tokens):
                if self._fail_after is not None and i == self._fail_after:
                    raise ProviderError("coupure")
                yield t
        except asyncio.CancelledError:
            self.cancelled = True
            raise


async def collect(gen):
    return "".join([t async for t in gen])


@pytest.mark.parametrize("text,level", [
    ("salut Jarvis", "instant"),
    ("merci", "instant"),
    ("vite, quelle est la capitale de l'Australie ?", "instant"),
    ("Explique-moi en détail comment fonctionne un transformeur dans un modèle de langage", "deep"),
    ("écris un script Python qui renomme mes photos par date", "deep"),
    ("réfléchis bien : dois-je changer de carte graphique ?", "deep"),
    ("quel film tu me conseilles pour ce soir avec des amis qui aiment la science-fiction", "standard"),
])
def test_classification(text, level):
    assert classify(text) == level


def test_resultat_outil_toujours_instant():
    assert classify("quel temps fait-il à Paris ?", tool_result_ready=True) == "instant"


async def test_le_plus_rapide_gagne_et_le_lent_est_annule():
    slow = FakeBrain("slow", delay=0.5, tokens=("lent",))
    fast = FakeBrain("fast", delay=0.01, tokens=("rapide",))
    winners = []

    async def on_winner(p, ttft):
        winners.append(p.name)

    text = await collect(hedged_stream([slow, fast], "", [], 100, Telemetry(), hedge_delay=0.05, on_winner=on_winner))
    assert text == "rapide"
    assert winners == ["fast"]
    assert slow.cancelled


async def test_pas_de_requete_en_double_si_le_premier_repond_vite():
    first = FakeBrain("first", delay=0.0, tokens=("a", "b"))
    second = FakeBrain("second")
    assert await collect(hedged_stream([first, second], "", [], 100, Telemetry(), hedge_delay=1.0)) == "ab"
    assert second.calls == 0


async def test_bascule_si_le_premier_echoue():
    tel = Telemetry()
    broken = FakeBrain("broken", fail=True)
    backup = FakeBrain("backup", tokens=("secours",))
    assert await collect(hedged_stream([broken, backup], "", [], 100, tel, hedge_delay=5)) == "secours"
    assert tel.get(brain_key(broken)).failures == 1
    assert tel.get(brain_key(backup)).ok == 1


async def test_tous_en_echec():
    with pytest.raises(ProviderError):
        await collect(hedged_stream([FakeBrain("a", fail=True), FakeBrain("b", fail=True)], "", [], 100, Telemetry(), 5))


async def test_coupure_apres_le_premier_token_leve_une_erreur():
    brain = FakeBrain("x", tokens=("un", "deux"), fail_after=1)
    out = []
    with pytest.raises(ProviderError):
        async for t in hedged_stream([brain], "", [], 100, Telemetry(), 5):
            out.append(t)
    assert out == ["un"]


def test_quarantaine_et_tri_par_latence():
    tel = Telemetry()
    a, b, c = FakeBrain("a"), FakeBrain("b"), FakeBrain("c")
    tel.failure(brain_key(a), "x")
    tel.failure(brain_key(a), "x")  # 2 échecs d'affilée → quarantaine
    tel.success(brain_key(c), ttft=0.2, tokens=10, duration=0.5)
    tel.success(brain_key(b), ttft=0.9, tokens=10, duration=1.5)
    assert [p.name for p in order_candidates("instant", [a, b, c], tel)] == ["c", "b"]
    assert [p.name for p in order_candidates("deep", [a, b, c], tel)] == ["b", "c"]


class FakeLocalManager:
    is_available = True
    model_name = "fake-gguf"

    async def stream(self, messages, max_tokens=512, system=None):
        yield "local"


def test_mode_auto_persistant_et_chaines(tmp_path):
    pm = ProviderManager(FakeLocalManager(), tmp_path)
    pm.configure("gemini", {"api_key": "AIza-test"})
    pm.configure("groq", {"api_key": "gsk-test"})
    assert pm.set_active("auto") == ""
    assert pm.is_auto
    instant = [f"{p.name}@{p.model}" for p in pm.candidates("instant")]
    assert instant[0].startswith("groq@")
    assert "gemini@gemini-2.5-flash-lite" in instant
    assert [p.model for p in pm.candidates("deep")] == ["gemini-2.5-pro", "gemini-2.5-flash"]
    assert pm.set_routing({"deep": ["gemini@gemini-2.5-flash"]}) == ""
    reloaded = ProviderManager(FakeLocalManager(), tmp_path)
    assert reloaded.is_auto
    assert [p.model for p in reloaded.candidates("deep")] == ["gemini-2.5-flash"]
    assert "invalide" in pm.set_routing({"deep": ["skynet@t800"]})
    status = pm.status()
    assert status["active"] == "auto"
    assert "AIza" not in str(status)


async def test_mode_auto_retombe_sur_le_local(tmp_path):
    pm = ProviderManager(FakeLocalManager(), tmp_path)
    assert pm.set_active("auto") == ""
    assert await collect(pm.stream("", [{"role": "user", "content": "salut"}], level="instant")) == "local"
