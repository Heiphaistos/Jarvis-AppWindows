from __future__ import annotations

from core.memory import ContextMemory
from utils.logger import get_logger

logger = get_logger("conversation_memory")

# Mémoire de conversation, deux horizons :
#   - résumé glissant : les messages qui sortent de la fenêtre de contexte sont
#     condensés, JARVIS garde le fil d'une longue discussion ;
#   - épisodes : chaque session est résumée et stockée, JARVIS peut répondre à
#     « de quoi on a parlé hier ? » et reprendre un sujet d'une fois sur l'autre.
# Les deux utilisent le cerveau cloud le plus rapide, jamais le 7B local.

EPISODE_EVERY_TURNS = 6     # résumé d'épisode mis à jour tous les N messages de Monsieur
MIN_TURNS_FOR_EPISODE = 2   # une salutation isolée ne fait pas un épisode
SUMMARY_MAX_CHARS = 1200
EPISODE_MAX_CHARS = 600

_ROLLING_SYSTEM = (
    "Tu condenses le début d'une conversation entre Monsieur et JARVIS pour que JARVIS garde le fil. "
    "Écris en français un résumé factuel de 120 mots au plus : sujets abordés, décisions, informations "
    "données par Monsieur, questions restées ouvertes. Pas de phrase d'introduction."
)
_EPISODE_SYSTEM = (
    "Tu archives une conversation entre Monsieur et JARVIS. Écris en français 2 à 4 phrases, 80 mots au "
    "plus : de quoi il a été question, ce qui a été fait ou décidé, ce qui reste à faire. Style télégraphique, "
    "noms propres et chiffres conservés, pas de phrase d'introduction."
)


def _transcript(messages: list[dict[str, str]], per_message: int = 500) -> str:
    who = {"user": "Monsieur", "assistant": "JARVIS"}
    return "\n".join(
        f"{who.get(m['role'], m['role'])} : {m['content'][:per_message]}" for m in messages
    )


async def _ask_fast_brain(providers, system: str, content: str, max_tokens: int) -> str:
    if providers.tier == "local":
        return ""
    chunks: list[str] = []
    async for token in providers.stream(
        system, [{"role": "user", "content": content}], max_tokens=max_tokens, level="instant",
    ):
        chunks.append(token)
    text = "".join(chunks).strip()
    # Message d'erreur du routeur (tous les cerveaux injoignables) : pas un résumé.
    if not text or text.startswith(("Tous mes cerveaux", "[")):
        return ""
    return text


async def update_rolling_summary(providers, memory: ContextMemory) -> bool:
    """Condense les messages sortis de la fenêtre dans memory.summary."""
    evicted = memory.take_evicted()
    if not evicted:
        return False
    content = ""
    if memory.summary:
        content += f"Résumé existant :\n{memory.summary}\n\n"
    content += f"Suite de la conversation à intégrer :\n{_transcript(evicted)}\n\nNouveau résumé :"
    try:
        summary = await _ask_fast_brain(providers, _ROLLING_SYSTEM, content, 350)
    except Exception as e:
        logger.warning(f"Résumé glissant impossible : {e}")
        summary = ""
    if not summary:
        # Pas de cerveau rapide : on remet les messages en attente pour la prochaine fois
        # (bornés pour ne pas grossir indéfiniment).
        memory.evicted = (evicted + memory.evicted)[-40:]
        return False
    memory.summary = summary[:SUMMARY_MAX_CHARS]
    logger.info(f"Résumé glissant mis à jour ({len(evicted)} messages condensés)")
    return True


async def save_episode(providers, memory: ContextMemory, episode_id: int | None) -> int | None:
    """Résume la session en cours et l'archive (création ou mise à jour). Retourne l'id."""
    if memory.user_turns < MIN_TURNS_FOR_EPISODE:
        return episode_id
    content = ""
    if memory.summary:
        content += f"Début de la conversation (résumé) :\n{memory.summary}\n\n"
    content += f"Conversation :\n{_transcript(memory.get_messages(), 400)}\n\nArchive :"
    try:
        summary = await _ask_fast_brain(providers, _EPISODE_SYSTEM, content, 250)
    except Exception as e:
        logger.warning(f"Archivage de la conversation impossible : {e}")
        return episode_id
    if not summary:
        return episode_id
    from core.persistent_memory import get_memory
    new_id = get_memory().save_episode(summary[:EPISODE_MAX_CHARS], episode_id)
    logger.info(f"Épisode {new_id} archivé")
    return new_id


def conversation_block(memory: ContextMemory) -> str:
    """Bloc de prompt : le début de la conversation en cours, condensé."""
    if not memory.summary:
        return ""
    return f"\n\n## PLUS TÔT DANS CETTE CONVERSATION (résumé)\n\n{memory.summary}"
