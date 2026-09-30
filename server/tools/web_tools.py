from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from tools.decorator import tool
from utils.logger import get_logger

logger = get_logger("web_tools")

_RESEARCH_SOURCES_MAX = 6
_PASSAGE_CHARS = 1400      # extraits gardés par source
_STOPWORDS = {
    "avec", "dans", "pour", "sont", "quel", "quelle", "quels", "quelles", "comment", "pourquoi",
    "est-ce", "cette", "entre", "plus", "moins", "faire", "fait", "tout", "tous", "leur", "leurs",
    "what", "which", "with", "from", "that", "this", "have", "does",
}


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web (DuckDuckGo, Bing fallback) and return top results as plain text."""
    if not isinstance(query, str) or not query.strip():
        return "Erreur: requête vide."
    from core.web_search import search
    try:
        results = search(query.strip(), max(1, min(int(max_results), 8)))
    except Exception as e:
        logger.error(f"Erreur recherche web: {e}")
        return f"Erreur recherche: {e}"
    if not results:
        return f"Aucun résultat pour: {query}"
    lines = [f"Résultats web — '{query}':"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.title}**\n   {r.snippet[:300]}\n   {r.url}")
    return "\n\n".join(lines)


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ0-9]{4,}", text.lower()) if w not in _STOPWORDS}


def best_passages(text: str, question: str, budget: int = _PASSAGE_CHARS) -> str:
    """Garde les paragraphes d'une page qui parlent le plus de la question,
    dans leur ordre d'origine, jusqu'au budget de caractères."""
    words = _keywords(question)
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) > 40]
    if not paragraphs:
        return text[:budget]
    hits = [sum(1 for w in words if w in p.lower()) for p in paragraphs]
    # Seuls les paragraphes qui parlent de la question (menus, cookies écartés) ;
    # aucun ne correspond → début de la page.
    ranked = sorted((i for i in range(len(paragraphs)) if hits[i]), key=lambda i: (-hits[i], i))
    if not ranked:
        ranked = list(range(len(paragraphs)))
    chosen, used = [], 0
    for i in ranked:
        if used >= budget:
            break
        chosen.append(i)
        used += len(paragraphs[i])
    out = "\n".join(paragraphs[i] for i in sorted(chosen))
    return out[:budget] + ("…" if len(out) > budget else "")


def _fetch(url: str) -> tuple[str, str]:
    from tools.assistant_tools import read_webpage
    page = read_webpage(url)
    if page.startswith(("Lecture impossible", "Contenu non textuel")):
        raise ValueError(page)
    return url, page


@tool
def deep_research(question: str, max_sources: int = 4) -> str:
    """Deep web research: searches, reads several sources in parallel and returns a sourced dossier to synthesise with citations [n]. Use for questions needing up-to-date facts, comparisons or verification across sources."""
    if not isinstance(question, str) or not question.strip():
        return "Erreur: question vide."
    question = question.strip()
    try:
        max_sources = max(2, min(int(max_sources), _RESEARCH_SOURCES_MAX))
    except (TypeError, ValueError):
        max_sources = 4
    from core.web_search import search
    try:
        results = search(question, 10)
    except Exception as e:
        return f"Erreur recherche: {e}"
    if not results:
        return f"Aucun résultat pour: {question}"

    # Un seul lien par site : des sources variées valent mieux que 4 pages du même domaine.
    picked, domains = [], set()
    for r in results:
        domain = urlparse(r.url).netloc.removeprefix("www.")
        if domain and domain not in domains:
            domains.add(domain)
            picked.append(r)
    candidates = picked[: max_sources + 2]  # marge : certaines pages refusent la lecture

    pages: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        for future in [pool.submit(_fetch, r.url) for r in candidates]:
            try:
                url, page = future.result(timeout=20)
                pages[url] = page
            except Exception as e:
                logger.info(f"Source ignorée : {e}")

    sections, n = [], 0
    for r in candidates:
        if n >= max_sources:
            break
        n += 1
        page = pages.get(r.url)
        body = best_passages(page, question) if page else f"(page illisible — extrait du moteur) {r.snippet}"
        sections.append(f"[{n}] {r.title}\n{r.url}\n{body}")
    if not sections:
        return f"Aucune source lisible pour: {question}"
    logger.info(f"Recherche approfondie : {len(pages)} page(s) lue(s) sur {len(candidates)}")
    return (
        f"DOSSIER DE RECHERCHE — « {question} » ({n} sources)\n\n"
        + "\n\n".join(sections)
        + "\n\nConsigne : synthétise une réponse complète et structurée à partir de ces sources, "
        "cite-les avec [n], signale les contradictions entre sources et ce qui reste incertain."
    )
