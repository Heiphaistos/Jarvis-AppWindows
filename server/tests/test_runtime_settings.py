"""Réglages modifiables depuis l'interface (data/settings.json)."""
import pytest

from utils.runtime_settings import RuntimeSettings, SettingsError


@pytest.fixture
def rs(tmp_path):
    return RuntimeSettings(tmp_path / "settings.json")


def test_valeurs_par_defaut(rs):
    assert rs.get("voice.end_silence_ms") == 1200
    assert rs.get("voice.stt_engine") == "auto"


def test_mise_a_jour_persistee(tmp_path, rs):
    rs.update({"voice.end_silence_ms": "1800", "voice.cloud_stt": False})
    relu = RuntimeSettings(tmp_path / "settings.json")
    assert relu.get("voice.end_silence_ms") == 1800
    assert relu.get("voice.cloud_stt") is False


def test_tout_ou_rien(rs):
    with pytest.raises(SettingsError):
        rs.update({"voice.end_silence_ms": 1500, "voice.stt_engine": "inconnu"})
    assert rs.get("voice.end_silence_ms") == 1200


@pytest.mark.parametrize("cle,valeur", [
    ("voice.speech_threshold", 5),
    ("voice.end_silence_ms", 10),
    ("voice.stt_language", "français"),
    ("live.model", "modele avec espaces"),
    ("nitrite.agent_path", r"C:\Windows\System32\calc.exe"),
    ("reglage.inconnu", 1),
])
def test_valeurs_refusees(rs, cle, valeur):
    with pytest.raises(SettingsError):
        rs.update({cle: valeur})


def test_chemin_agent_nitrite_accepte(rs):
    chemin = r"C:\Users\moi\Downloads\NiTriTe-Agent-1.5.0.exe"
    rs.update({"nitrite.agent_path": chemin})
    assert rs.get("nitrite.agent_path") == chemin


def test_variable_environnement_comme_defaut(rs, monkeypatch):
    monkeypatch.setenv("JARVIS_CLOUD_STT", "0")
    assert rs.get("voice.cloud_stt") is False
    rs.update({"voice.cloud_stt": True})
    assert rs.get("voice.cloud_stt") is True


def test_moteur_local_coupe_le_cloud(monkeypatch):
    from core import cloud_stt

    class FakeProviders:
        _configs = {}

        def api_key(self, name):
            return "cle"

    monkeypatch.setattr("utils.runtime_settings.setting",
                        lambda k: {"voice.cloud_stt": True, "voice.stt_engine": "local"}.get(k, "x"))
    assert cloud_stt.engines(FakeProviders()) == []
    monkeypatch.setattr("utils.runtime_settings.setting",
                        lambda k: {"voice.cloud_stt": True, "voice.stt_engine": "openai",
                                   "voice.openai_stt_model": "gpt-4o-mini-transcribe"}.get(k, "x"))
    assert [e[0] for e in cloud_stt.engines(FakeProviders())] == ["openai"]


def test_consignes_multilignes(tmp_path):
    from utils.runtime_settings import RuntimeSettings, SettingsError
    rs = RuntimeSettings(tmp_path / "settings.json")
    rs.update({"assistant.instructions": "Appelle-moi Tony.\r\nRéponds court."})
    assert rs.get("assistant.instructions") == "Appelle-moi Tony.\nRéponds court."
    with pytest.raises(SettingsError):
        rs.update({"tts.gemini_style": "ligne 1\nligne 2"})
    with pytest.raises(SettingsError):
        rs.update({"assistant.response_length": "infinie"})


def test_consignes_dans_le_prompt(monkeypatch):
    import utils.runtime_settings as rt
    from core.prompt import build_system_prompt
    monkeypatch.setattr(rt, "setting", lambda key: "Appelle-moi Tony." if key == "assistant.instructions" else rt.SPECS[key].default)
    assert "Appelle-moi Tony." in build_system_prompt("cloud", "bonjour")
