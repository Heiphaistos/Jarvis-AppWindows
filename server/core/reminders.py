from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("reminders")

MAX_REMINDERS = 50


@dataclass
class Reminder:
    id: int
    due: float        # timestamp epoch (s)
    message: str
    kind: str         # "timer" | "reminder" | "routine"
    created: float
    # Routines (récurrentes) : heure « HH:MM », jours 0=lundi … 6=dimanche, action.
    at: str = ""
    days: list[int] | None = None
    action: str = "message"   # "message" | "briefing" | "pc_check"


ROUTINE_ACTIONS = ("message", "briefing", "pc_check")
# PC éteint à l'heure prévue : une routine en retard de plus d'une heure est
# reportée à la prochaine occurrence au lieu de se déclencher à l'allumage.
ROUTINE_GRACE_S = 3600
DAY_NAMES = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def next_occurrence(at: str, days: list[int], after: datetime) -> datetime:
    """Prochaine date strictement après `after` à l'heure `at` un des jours `days`."""
    hour, minute = (int(x) for x in at.split(":"))
    for offset in range(8):
        day = after.date() + timedelta(days=offset)
        candidate = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
        if candidate > after and candidate.weekday() in days:
            return candidate
    raise ValueError("aucun jour valide")


class ReminderStore:
    """Minuteurs et rappels persistants (JSON), déclenchés dans la boucle asyncio.

    Les outils tournent dans des threads (asyncio.to_thread) : l'ajout est
    protégé par un verrou et le réveil de la boucle passe par
    call_soon_threadsafe. À l'échéance, `on_due(reminder)` est appelé dans la boucle.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._items: dict[int, Reminder] = {}
        self._next_id = 1
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wake: asyncio.Event | None = None
        self._on_due = None
        self._load()

    # ── Persistance ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for raw in data.get("items", []):
                r = Reminder(**raw)
                self._items[r.id] = r
            self._next_id = int(data.get("next_id", max(self._items, default=0) + 1))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Rappels illisibles ({e}) — liste vide")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps({
                "next_id": self._next_id,
                "items": [asdict(r) for r in self._items.values()],
            }, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Sauvegarde des rappels impossible: {e}")

    # ── API (appelable depuis n'importe quel thread) ─────────────────────────
    def add(self, delay_s: float, message: str, kind: str) -> Reminder:
        with self._lock:
            if len(self._items) >= MAX_REMINDERS:
                raise ValueError(f"{MAX_REMINDERS} rappels maximum")
            r = Reminder(self._next_id, time.time() + delay_s, message.strip()[:300], kind, time.time())
            self._items[r.id] = r
            self._next_id += 1
            self._save()
        self._poke()
        return r

    def add_routine(self, at: str, days: list[int], action: str, message: str = "") -> Reminder:
        if action not in ROUTINE_ACTIONS:
            raise ValueError(f"action inconnue : {action}")
        days = sorted({int(d) for d in days if 0 <= int(d) <= 6})
        if not days:
            raise ValueError("aucun jour")
        due = next_occurrence(at, days, datetime.now()).timestamp()
        with self._lock:
            if len(self._items) >= MAX_REMINDERS:
                raise ValueError(f"{MAX_REMINDERS} rappels maximum")
            r = Reminder(self._next_id, due, message.strip()[:300], "routine", time.time(),
                         at=at, days=days, action=action)
            self._items[r.id] = r
            self._next_id += 1
            self._save()
        self._poke()
        return r

    def cancel(self, reminder_id: int) -> bool:
        with self._lock:
            found = self._items.pop(int(reminder_id), None) is not None
            if found:
                self._save()
        self._poke()
        return found

    def pending(self) -> list[Reminder]:
        with self._lock:
            return sorted(self._items.values(), key=lambda r: r.due)

    def _poke(self) -> None:
        if self._loop is not None and self._wake is not None:
            self._loop.call_soon_threadsafe(self._wake.set)

    # ── Boucle de déclenchement ──────────────────────────────────────────────
    async def run(self, on_due) -> None:
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._on_due = on_due
        while True:
            now = time.time()
            due = [r for r in self.pending() if r.due <= now]
            for r in due:
                late = now - r.due
                with self._lock:
                    if r.days:
                        # Routine : reprogrammée à la prochaine occurrence, jamais supprimée.
                        r.due = next_occurrence(r.at, r.days, datetime.fromtimestamp(now)).timestamp()
                    else:
                        self._items.pop(r.id, None)
                    self._save()
                if r.days and late > ROUTINE_GRACE_S:
                    logger.info(f"Routine #{r.id} manquée ({late / 3600:.1f} h de retard) — reportée")
                    continue
                try:
                    await on_due(r)
                except Exception as e:
                    logger.error(f"Rappel #{r.id} non délivré: {e}")
            upcoming = self.pending()
            timeout = max(0.2, min(60.0, upcoming[0].due - time.time())) if upcoming else 60.0
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass


def describe_days(days: list[int]) -> str:
    if sorted(days) == list(range(7)):
        return "tous les jours"
    if sorted(days) == list(range(5)):
        return "en semaine"
    if sorted(days) == [5, 6]:
        return "le week-end"
    return ", ".join(DAY_NAMES[d] for d in sorted(days))


_ACTION_LABELS = {"briefing": "briefing", "pc_check": "contrôle de santé du PC"}


def describe(r: Reminder) -> str:
    if r.days:
        what = _ACTION_LABELS.get(r.action) or r.message
        nxt = datetime.fromtimestamp(r.due)
        return f"#{r.id} Routine {describe_days(r.days)} à {r.at} — {what} (prochaine : {nxt:%d/%m %H:%M})"
    when = datetime.fromtimestamp(r.due)
    label = "Minuteur" if r.kind == "timer" else "Rappel"
    return f"#{r.id} {label} {when.strftime('%d/%m %H:%M:%S')} — {r.message}"


_store: ReminderStore | None = None


def init_reminders(path: Path) -> ReminderStore:
    global _store
    _store = ReminderStore(path)
    return _store


def get_reminders() -> ReminderStore:
    if _store is None:
        raise RuntimeError("Rappels non initialisés")
    return _store
