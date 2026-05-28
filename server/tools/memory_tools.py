from __future__ import annotations
from utils.logger import get_logger

logger = get_logger("memory_tools")


def save_memory(key: str, value: str, category: str = "general") -> str:
    """Save a persistent fact about the user or context."""
    if not isinstance(key, str) or not key.strip():
        return "Erreur: clé invalide (chaîne non vide requise)."
    if not isinstance(value, str) or not value.strip():
        return "Erreur: valeur invalide."
    from core.persistent_memory import get_memory
    return get_memory().save(key.strip(), value.strip(), category.strip() or "general")


def recall_memory(query: str) -> str:
    """Search persistent memories for a keyword."""
    if not isinstance(query, str) or not query.strip():
        return "Erreur: requête vide."
    from core.persistent_memory import get_memory
    return get_memory().recall(query.strip())


def list_memories(category: str = "") -> str:
    """List all stored memories, optionally filtered by category."""
    from core.persistent_memory import get_memory
    return get_memory().list_all(category.strip() if isinstance(category, str) else "")
