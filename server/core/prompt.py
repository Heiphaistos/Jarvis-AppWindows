from __future__ import annotations

from core.llm import SYSTEM_PROMPT
from core.skills import get_router
from utils.logger import get_logger

logger = get_logger("prompt")


def build_system_prompt(tier: str, user_text: str, stable: bool = False) -> str:
    """Compose le system prompt : base + disciplines Fable + mémoire + leçons.

    tier: "local" (variantes compactes) ou "cloud" (variantes complètes).
    stable: inclut TOUTES les disciplines (pas de routage par intent) — prompt
    identique d'un message à l'autre, indispensable pour préserver le cache KV
    llama-cpp en local (sinon ré-évaluation complète à chaque message).
    """
    parts = [SYSTEM_PROMPT]

    router = get_router()
    if stable:
        # Prompt stable ET court : seulement les disciplines `always` — un 7B
        # ne suit pas 6 disciplines, et chaque token de prompt coûte de la
        # latence au premier message.
        skills_block = "\n\n".join(
            f"### {s.name}\n{s.body(tier)}" for s in router.skills if s.always
        )
    else:
        skills_block = router.select(user_text, tier)
    if skills_block:
        parts.append(
            "\n\n## DISCIPLINES ACTIVES (à appliquer strictement)\n\n" + skills_block
        )

    try:
        from core.persistent_memory import get_memory
        memory = get_memory()
        ctx = memory.get_context_summary("" if stable else user_text)
        if ctx:
            parts.append(ctx)
        lessons = memory.get_lessons_summary()
        if lessons:
            parts.append(lessons)
    except Exception as e:
        logger.warning(f"Mémoire indisponible pour le prompt: {e}")

    # Rappel final (biais de récence) : sans lui, le 7B répond de mémoire au
    # lieu d'appeler les outils quand le prompt s'allonge.
    parts.append(
        "\n\n## RAPPEL CRITIQUE — OUTILS\n\n"
        "Pour toute question sur : météo, actualités, recherche web, heure/date, "
        "calcul, conversion, état système, fichiers, emails, presse-papiers — tu ne "
        "connais PAS la réponse. Tu DOIS d'abord émettre "
        '<JARVIS_TOOL>{"name": "...", "args": {...}}</JARVIS_TOOL> '
        "et attendre le résultat. Ne réponds JAMAIS de mémoire à ces questions. "
        'Exemple : « calcule 17*23 » → <JARVIS_TOOL>{"name": "calculate", '
        '"args": {"expression": "17*23"}}</JARVIS_TOOL>'
    )

    return "".join(parts)
