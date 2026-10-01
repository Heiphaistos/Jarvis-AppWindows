import random
from datetime import datetime

from core import connections as cx
from core.greeting import build_greeting


def test_accueil_selon_heure(tmp_path):
    cx.reset_store(tmp_path / "c.json")
    try:
        matin = build_greeting(datetime(2026, 10, 1, 8, 5), rng=random.Random(1))
        assert "Monsieur" in matin and "Il est 8 heures 05." in matin and "Bonsoir" not in matin
        soir = build_greeting(datetime(2026, 10, 1, 20, 0), title="Tony", rng=random.Random(2))
        assert "Tony" in soir and "Il est 20 heures." in soir
        nuit = build_greeting(datetime(2026, 10, 1, 2, 30), rng=random.Random(3))
        assert "Bonsoir" in nuit or "debout" in nuit
        # Sans compte connecté, aucune mention de mails
        assert "mail" not in build_greeting(datetime(2026, 10, 1, 14, 0), briefing=True)
    finally:
        cx.reset_store(None)


def test_appellation_validee(tmp_path):
    import pytest
    from utils.runtime_settings import RuntimeSettings, SettingsError
    rs = RuntimeSettings(tmp_path / "s.json")
    rs.update({"assistant.user_title": "Madame"})
    assert rs.get("assistant.user_title") == "Madame"
    with pytest.raises(SettingsError):
        rs.update({"assistant.user_title": "<script>"})
