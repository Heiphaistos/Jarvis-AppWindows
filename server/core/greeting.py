"""Accueil vocal à l'ouverture de l'application, façon JARVIS d'Iron Man.

Court (une dizaine de secondes à l'oral) : salutation selon l'heure, une
touche de majordome, puis — si des comptes sont connectés — les mails non lus
et le prochain rendez-vous. Chaque source a un délai court : l'accueil ne doit
jamais attendre un service lent.
"""
from __future__ import annotations

import random
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
from typing import Callable

from utils.logger import get_logger

logger = get_logger("greeting")

_SOURCE_TIMEOUT_S = 4.0

_OPENERS = {
    "night": ["Bonsoir, {t}. Vous travaillez tard, une fois de plus.", "Toujours debout, {t} ? Je reste à vos côtés."],
    "morning": ["Bonjour, {t}.", "Bonjour, {t}. J'espère que vous avez bien dormi.", "Bon retour parmi nous, {t}."],
    "afternoon": ["Bon après-midi, {t}.", "Ravi de vous revoir, {t}.", "Bon retour, {t}."],
    "evening": ["Bonsoir, {t}.", "Bonsoir, {t}. Ravi de vous revoir.", "Bon retour parmi nous, {t}."],
}
_STATUS = [
    "Tous les systèmes sont opérationnels.",
    "Tous les systèmes sont en ligne et à votre disposition.",
    "J'ai pris la liberté de vérifier les systèmes : tout est nominal.",
    "Le réacteur est stable et tous les systèmes répondent.",
]
_CLOSERS = [
    "Que puis-je faire pour vous ?",
    "Je suis à votre disposition.",
    "Par quoi commençons-nous ?",
]


def _moment(hour: int) -> str:
    if hour < 5 or hour >= 23:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _spoken_time(now: datetime) -> str:
    return f"Il est {now.hour} heure{'s' if now.hour > 1 else ''}" + (f" {now.minute:02d}" if now.minute else "") + "."


def _unread_mails() -> str:
    from core.connections import get_store
    if not get_store().is_configured("mail"):
        return ""
    from tools.connection_tools import _imap, _select
    conn = _imap()
    try:
        _select(conn, "INBOX")
        typ, data = conn.uid("SEARCH", None, "UNSEEN")
        n = len(data[0].split()) if typ == "OK" and data and data[0] else 0
    finally:
        conn.logout()
    if n == 0:
        return "Aucun nouveau mail."
    return f"Vous avez {n} mail{'s' if n > 1 else ''} non lu{'s' if n > 1 else ''}."


def _next_event() -> str:
    from core.connections import get_store
    if not get_store().is_configured("calendar"):
        return ""
    from datetime import timedelta
    from tools.connection_tools import _request, parse_ics
    url = get_store().value("calendar", "ics_url").replace("webcal://", "https://")
    now = datetime.now()
    events = [e for e in parse_ics(_request("GET", url, "Agenda").text, now, now + timedelta(hours=18)) if not e[1]]
    if not events:
        return ""
    when, _, title, _ = events[0]
    day = "demain " if when.date() != now.date() else ""
    return f"Prochain rendez-vous : {re.sub(r'[<>]', '', title)}, {day}à {when.hour} heure{'s' if when.hour > 1 else ''}" + \
        (f" {when.minute:02d}" if when.minute else "") + "."


def _gather(sources: list[Callable[[], str]]) -> list[str]:
    out: list[str] = []
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = [pool.submit(fn) for fn in sources]
        for fut in futures:
            try:
                text = fut.result(timeout=_SOURCE_TIMEOUT_S)
            except FutureTimeout:
                continue
            except Exception as e:  # noqa: BLE001 — l'accueil ne doit jamais échouer
                logger.info(f"Accueil : source ignorée ({e.__class__.__name__})")
                continue
            if text:
                out.append(text)
    return out


def build_greeting(now: datetime | None = None, briefing: bool = True, title: str = "Monsieur",
                   rng: random.Random | None = None) -> str:
    now = now or datetime.now()
    rng = rng or random.Random()
    title = title.strip() or "Monsieur"
    parts = [rng.choice(_OPENERS[_moment(now.hour)]).format(t=title), _spoken_time(now), rng.choice(_STATUS)]
    if briefing:
        parts.extend(_gather([_unread_mails, _next_event]))
    parts.append(rng.choice(_CLOSERS))
    return " ".join(parts)
