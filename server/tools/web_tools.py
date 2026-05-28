from __future__ import annotations
from utils.logger import get_logger

logger = get_logger("web_tools")


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web via DuckDuckGo and return top results as plain text."""
    if not query or not query.strip():
        return "Erreur: requête vide."
    try:
        from duckduckgo_search import DDGS  # type: ignore[import]
        results = list(DDGS().text(query.strip(), max_results=min(int(max_results), 8)))
        if not results:
            return f"Aucun résultat pour: {query}"
        lines = [f"Résultats web — '{query}':"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "Sans titre")
            body = (r.get("body") or "")[:300]
            url = r.get("href", "")
            lines.append(f"{i}. **{title}**\n   {body}\n   {url}")
        return "\n\n".join(lines)
    except ImportError:
        return "Module duckduckgo-search manquant — pip install duckduckgo-search"
    except Exception as e:
        logger.error(f"Erreur recherche web: {e}")
        return f"Erreur recherche: {e}"
