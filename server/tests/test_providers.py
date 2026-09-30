import json

import pytest

from core.providers.base import LLMProvider, ProviderError
from core.providers.manager import ProviderManager, PRESETS, _mask


class FakeLocalManager:
    """Double du LLMManager local."""
    is_available = True
    model_name = "fake-gguf"

    async def stream(self, messages, max_tokens=512, system=None):
        yield "réponse "
        yield "locale"


@pytest.fixture
def pm(tmp_path):
    return ProviderManager(FakeLocalManager(), tmp_path)


def test_defaut_local(pm):
    assert pm.active.name == "local"
    assert pm.tier == "local"
    assert pm.is_available


def test_configure_et_activer_anthropic(pm, tmp_path):
    assert pm.configure("anthropic", {"api_key": "sk-test-1234"}) == ""
    assert pm.set_active("anthropic") == ""
    assert pm.active.name == "anthropic"
    assert pm.tier == "cloud"
    # Persistance sur disque
    saved = json.loads((tmp_path / "providers.json").read_text(encoding="utf-8"))
    assert saved["active"] == "anthropic"
    assert saved["configs"]["anthropic"]["api_key"] == "sk-test-1234"


def test_activation_refusee_sans_cle(pm):
    error = pm.set_active("openai")
    assert "incomplet" in error
    assert pm.active.name == "local"


def test_provider_inconnu(pm):
    assert "inconnu" in pm.set_active("skynet")
    assert "inconnu" in pm.configure("skynet", {"api_key": "x"}).lower()


def test_base_url_invalide_rejetee(pm):
    assert "http" in pm.configure("custom", {"base_url": "ftp://nope"})


def test_cles_masquees_dans_status(pm):
    pm.configure("openai", {"api_key": "sk-abcdef123456"})
    status = pm.status()
    entry = next(p for p in status["providers"] if p["name"] == "openai")
    assert "sk-abcdef" not in entry["api_key_masked"]
    assert entry["api_key_masked"].endswith("3456")
    assert "sk-abcdef123456" not in json.dumps(status)


def test_rechargement_config_corrompue(tmp_path):
    (tmp_path / "providers.json").write_text("{invalid json", encoding="utf-8")
    pm = ProviderManager(FakeLocalManager(), tmp_path)
    assert pm.active.name == "local"


def test_actif_persiste_puis_invalide_retombe_local(tmp_path):
    (tmp_path / "providers.json").write_text(
        json.dumps({"active": "groq", "configs": {}}), encoding="utf-8"
    )
    pm = ProviderManager(FakeLocalManager(), tmp_path)
    assert pm.active.name == "local"


def test_mask():
    assert _mask("") == ""
    assert _mask("abc") == "••••"
    assert _mask("sk-12345678") == "••••5678"


class FailingProvider(LLMProvider):
    name = "failing"
    label = "Failing"
    tier = "cloud"
    is_available = True
    model = "boom"

    async def stream(self, system, messages, max_tokens=512, tools=None):
        raise ProviderError("panne réseau")
        yield  # pragma: no cover


@pytest.mark.asyncio
async def test_fallback_local_sur_echec_cloud(pm, monkeypatch):
    monkeypatch.setattr(ProviderManager, "active", property(lambda self: FailingProvider()))
    fallbacks = []

    async def on_fallback(label):
        fallbacks.append(label)

    tokens = [t async for t in pm.stream("sys", [{"role": "user", "content": "hi"}],
                                         on_fallback=on_fallback)]
    assert "".join(tokens) == "réponse locale"
    assert fallbacks == ["Failing"]


def test_tous_les_presets_construisibles():
    for name, preset in PRESETS.items():
        assert preset["kind"] in ("anthropic", "openai")
        assert "label" in preset
