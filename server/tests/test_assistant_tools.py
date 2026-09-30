import asyncio
import time

import pytest

from core.reminders import ReminderStore, init_reminders
from tools.assistant_tools import html_to_text, set_reminder, set_timer, list_reminders, cancel_reminder, media_control


@pytest.fixture
def store(tmp_path):
    return init_reminders(tmp_path / "reminders.json")


def test_minuteur_et_annulation(store):
    assert "Minuteur #1" in set_timer(5, "thé")
    assert "thé" in list_reminders()
    assert "annulé" in cancel_reminder(1)
    assert "Aucun" in list_reminders()


def test_formats_de_rappel(store):
    assert "Rappel #1" in set_reminder("dans 20 min", "sortir le linge")
    assert "Rappel #2" in set_reminder("18:30", "appeler maman")
    assert "Rappel #3" in set_reminder("9h", "réunion")
    assert "non reconnu" in set_reminder("bientôt", "x")
    due = store.pending()[0].due
    assert 19 * 60 < due - time.time() <= 20 * 60


def test_persistance(tmp_path):
    a = ReminderStore(tmp_path / "r.json")
    a.add(600, "persiste", "reminder")
    b = ReminderStore(tmp_path / "r.json")
    assert [r.message for r in b.pending()] == ["persiste"]


async def test_declenchement(tmp_path):
    s = ReminderStore(tmp_path / "r.json")
    fired = []

    async def on_due(r):
        fired.append(r.message)

    task = asyncio.create_task(s.run(on_due))
    await asyncio.sleep(0.05)
    await asyncio.to_thread(s.add, 0.1, "ding", "timer")  # ajout depuis un thread, comme un outil
    await asyncio.sleep(0.6)
    task.cancel()
    assert fired == ["ding"]
    assert s.pending() == []


def test_extraction_html():
    title, text = html_to_text(
        "<html><head><title>Arc Reactor</title><style>.x{}</style></head>"
        "<body><nav>menu</nav><h1>Réacteur</h1><p>Énergie &amp; propreté.</p><script>evil()</script></body></html>"
    )
    assert title == "Arc Reactor"
    assert "Énergie & propreté." in text and "menu" not in text and "evil" not in text


def test_media_action_inconnue():
    assert "inconnue" in media_control("danser")
