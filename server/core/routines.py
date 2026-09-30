from __future__ import annotations

import asyncio

from utils.logger import get_logger

logger = get_logger("routines")

# Exécution des routines programmées (voir core/reminders.py) :
#   briefing  : le briefing complet, condensé en quelques phrases à dire ;
#   pc_check  : contrôle santé via NiTriTe — ne parle QUE s'il y a un problème ;
#   message   : un rappel récurrent (« tous les soirs, pense à tes médicaments »).

_SPOKEN_SYSTEM = (
    "Tu es JARVIS. Transforme ces informations brutes en un briefing parlé de 4 à 6 phrases "
    "naturelles, ton posé de majordome, en commençant par saluer Monsieur selon l'heure. "
    "Garde la date, la météo, les rappels du jour, une alerte éventuelle sur le PC et deux ou "
    "trois titres d'actualité. Pas de liste, de symbole ni de lien."
)


async def _spoken(providers, raw: str) -> str:
    """Résumé parlé par le cerveau rapide ; à défaut, les premières lignes utiles."""
    if providers is not None and providers.tier == "cloud":
        try:
            chunks = [t async for t in providers.stream(
                _SPOKEN_SYSTEM, [{"role": "user", "content": raw[:6000]}], max_tokens=400, level="instant",
            )]
            text = "".join(chunks).strip()
            if text and not text.startswith(("Tous mes cerveaux", "[")):
                return text
        except Exception as e:
            logger.warning(f"Résumé du briefing impossible : {e}")
    lines = [line.strip() for line in raw.splitlines() if line.strip() and not line.startswith(("#", "-", "|"))]
    return " ".join(lines[:6])[:600]


async def run(reminder, providers) -> str | None:
    """Texte à annoncer pour une routine échue, ou None si rien à dire."""
    if reminder.action == "briefing":
        from tools.assistant_tools import briefing
        raw = await asyncio.to_thread(briefing)
        return await _spoken(providers, raw)
    if reminder.action == "pc_check":
        from core import nitrite
        if not await asyncio.to_thread(nitrite.is_running):
            return None  # pas d'agent : pas de fausse alerte ni de bavardage
        from tools.pc_tools import TOPICS, _collect, alerts
        sections = TOPICS["batterie"] + TOPICS["disques"] + TOPICS["temperatures"] + TOPICS["sante"]
        try:
            raw, _, _ = await asyncio.to_thread(_collect, sections)
        except Exception as e:
            logger.warning(f"Contrôle santé impossible : {e}")
            return None
        found = [a for a in alerts(raw) if not a.startswith("Info")]
        return ("Contrôle de santé du PC : " + " ".join(found)) if found else None
    return reminder.message or None
