import asyncio
import time
from datetime import datetime

import pytest

from core import reminders as rm
from core import routines
from tools.assistant_tools import parse_days


def test_prochaine_occurrence():
    wed_10h = datetime(2026, 9, 30, 10, 0)  # mercredi
    assert rm.next_occurrence("08:00", list(range(7)), wed_10h) == datetime(2026, 10, 1, 8, 0)
    assert rm.next_occurrence("11:30", list(range(7)), wed_10h) == datetime(2026, 9, 30, 11, 30)
    assert rm.next_occurrence("08:00", [5, 6], wed_10h) == datetime(2026, 10, 3, 8, 0)  # samedi
    assert rm.next_occurrence("10:00", [2], wed_10h) == datetime(2026, 10, 7, 10, 0)  # strictement après


@pytest.mark.parametrize("text,days", [
    ("tous les jours", [0, 1, 2, 3, 4, 5, 6]),
    ("en semaine", [0, 1, 2, 3, 4]),
    ("le week-end", [5, 6]),
    ("lundi et jeudi", [0, 3]),
    ("les mardis", [1]),
    ("lundi-vendredi", [0, 1, 2, 3, 4]),
    ("vendredi au lundi", [4, 5, 6, 0]),
    ("jamais", []),
])
def test_jours(text, days):
    assert parse_days(text) == days


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = rm.ReminderStore(tmp_path / "rem.json")
    monkeypatch.setattr(rm, "_store", s)
    return s


def test_outil_set_routine(store):
    from tools.assistant_tools import set_routine
    out = set_routine("7h30", "briefing", "en semaine")
    assert "Routine en semaine à 07:30 — briefing" in out
    assert "Précisez le message" in set_routine("20:00", "message")
    assert "Heure non reconnue" in set_routine("dans 5 min")
    [r] = store.pending()
    assert r.kind == "routine" and r.days == [0, 1, 2, 3, 4] and r.at == "07:30"
    # Persistée puis relue (anciens fichiers sans champs de routine compris).
    again = rm.ReminderStore(store._path)
    assert again.pending()[0].days == [0, 1, 2, 3, 4]


async def test_routine_reprogrammee_pas_supprimee(store):
    r = store.add_routine("08:00", list(range(7)), "message", "Médicaments")
    r.due = time.time() - 5  # échue il y a 5 s
    fired = []

    async def on_due(x):
        fired.append(x.message)

    task = asyncio.create_task(store.run(on_due))
    await asyncio.sleep(0.3)
    task.cancel()
    assert fired == ["Médicaments"]
    [still] = store.pending()
    assert still.due > time.time()  # prochaine occurrence


async def test_routine_trop_en_retard_reportee(store):
    r = store.add_routine("08:00", list(range(7)), "briefing")
    r.due = time.time() - 5 * 3600  # PC éteint à 8 h, allumé à 13 h
    fired = []

    async def on_due(x):
        fired.append(x)

    task = asyncio.create_task(store.run(on_due))
    await asyncio.sleep(0.3)
    task.cancel()
    assert fired == [] and store.pending()[0].due > time.time()


class Providers:
    tier = "cloud"

    async def stream(self, system, messages, **kw):
        assert "briefing parlé" in system
        yield "Bonjour Monsieur, nous sommes mercredi et il fait 18 degrés à Lyon."


async def test_briefing_parle(monkeypatch):
    import tools.assistant_tools as at
    monkeypatch.setattr(at, "briefing", lambda city="": "Mercredi 30/09\nMétéo à Lyon : 18°C")
    r = rm.Reminder(1, 0, "", "routine", 0, at="08:00", days=[2], action="briefing")
    assert (await routines.run(r, Providers())).startswith("Bonjour Monsieur")

    class Local:
        tier = "local"
    assert await routines.run(r, Local()) == "Mercredi 30/09 Météo à Lyon : 18°C"


async def test_controle_pc_muet_si_tout_va_bien(monkeypatch):
    from core import nitrite
    import tools.pc_tools as pc
    r = rm.Reminder(1, 0, "", "routine", 0, at="09:00", days=[0], action="pc_check")
    monkeypatch.setattr(nitrite, "is_running", lambda: False)
    assert await routines.run(r, None) is None
    monkeypatch.setattr(nitrite, "is_running", lambda: True)
    monkeypatch.setattr(pc, "_collect", lambda sections: ({"get_disks_smart": [{"label": "SSD", "health": "Healthy"}]}, {}, []))
    assert await routines.run(r, None) is None
    monkeypatch.setattr(pc, "_collect", lambda sections: ({"get_disks_smart": [{"label": "SSD", "health": "Unhealthy"}]}, {}, []))
    assert "SSD : état SMART « Unhealthy »" in await routines.run(r, None)
