from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

from utils.logger import get_logger

logger = get_logger("web_search")

# Recherche web SANS dépendance : la bibliothèque duckduckgo_search n'était
# pas installée par requirements.txt, web_search et get_news échouaient donc
# sur une installation neuve. Moteurs essayés dans l'ordre, le premier qui
# répond gagne : DuckDuckGo (HTML) → Bing (RSS) → bibliothèque ddgs si présente.
# Actualités : Google News (RSS) → Bing News (RSS).

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
_TIMEOUT = 10


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str = ""
    date: str = ""


def _get(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": _UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
    })
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read(1_500_000).decode(resp.headers.get_content_charset() or "utf-8", errors="replace")


def _clean(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# ── DuckDuckGo (HTML) ─────────────────────────────────────────────────────────

_DDG_LINK = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DDG_SNIPPET = re.compile(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div|td)>', re.S)


def _ddg_target(href: str) -> str:
    """Les liens DuckDuckGo passent par /l/?uddg=<url encodée> : on récupère la vraie URL."""
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return target
    return href


def parse_duckduckgo(page: str) -> list[SearchResult]:
    results: list[SearchResult] = []
    # Chaque résultat est un bloc « result » ; le découpage garde lien et extrait ensemble.
    blocks = re.split(r'<div[^>]+class="[^"]*\bresult\b', page)[1:] or [page]
    for block in blocks:
        link = _DDG_LINK.search(block)
        if not link:
            continue
        url = _ddg_target(link.group(1))
        if "duckduckgo.com/y.js" in url or not url.startswith("http"):
            continue  # publicité
        snippet = _DDG_SNIPPET.search(block)
        results.append(SearchResult(_clean(link.group(2)), url, _clean(snippet.group(1)) if snippet else ""))
    return results


def _search_duckduckgo(query: str) -> list[SearchResult]:
    page = _get("https://html.duckduckgo.com/html/", urllib.parse.urlencode({"q": query, "kl": "fr-fr"}).encode())
    return parse_duckduckgo(page)


# ── RSS (Bing, Google News) ──────────────────────────────────────────────────

def parse_rss(xml_text: str) -> list[SearchResult]:
    try:
        root = ET.fromstring(xml_text.strip().encode("utf-8"))
    except ET.ParseError:
        return []
    results: list[SearchResult] = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title") or "")
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        source = _clean(item.findtext("source") or "")
        # Google News : « Titre - Journal » ; la source est déjà dans <source>.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        date = ""
        pub = item.findtext("pubDate")
        if pub:
            try:
                date = parsedate_to_datetime(pub).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                date = pub[:16]
        results.append(SearchResult(title, url, _clean(item.findtext("description") or "")[:400], source, date))
    return results


def _search_bing(query: str) -> list[SearchResult]:
    q = urllib.parse.urlencode({"q": query, "format": "rss", "setlang": "fr"})
    return parse_rss(_get(f"https://www.bing.com/search?{q}"))


def _search_ddgs_lib(query: str) -> list[SearchResult]:
    try:
        from ddgs import DDGS  # type: ignore[import]
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore[import]
    return [
        SearchResult(r.get("title", ""), r.get("href", ""), r.get("body", ""))
        for r in DDGS().text(query, max_results=10)
    ]


def _news_google(query: str) -> list[SearchResult]:
    base = "https://news.google.com/rss"
    params = {"hl": "fr", "gl": "FR", "ceid": "FR:fr"}
    url = f"{base}/search?{urllib.parse.urlencode({'q': query, **params})}" if query else f"{base}?{urllib.parse.urlencode(params)}"
    return parse_rss(_get(url))


def _news_bing(query: str) -> list[SearchResult]:
    q = urllib.parse.urlencode({"q": query or "actualités", "format": "rss", "setlang": "fr"})
    return parse_rss(_get(f"https://www.bing.com/news/search?{q}"))


# ── Points d'entrée ──────────────────────────────────────────────────────────

def _first_that_answers(engines, query: str, max_results: int) -> list[SearchResult]:
    errors = []
    for engine in engines:
        try:
            results = [r for r in engine(query) if r.url.startswith("http")]
        except Exception as e:  # moteur bloqué, hors ligne, format changé…
            errors.append(f"{engine.__name__}: {e}")
            continue
        if results:
            # Un même site cité deux fois n'apporte rien : un résultat par URL.
            seen, unique = set(), []
            for r in results:
                if r.url not in seen:
                    seen.add(r.url)
                    unique.append(r)
            return unique[:max_results]
    if errors:
        logger.warning("Recherche sans résultat : " + " | ".join(errors))
        raise ConnectionError("aucun moteur de recherche joignable")
    return []


def search(query: str, max_results: int = 8) -> list[SearchResult]:
    return _first_that_answers((_search_duckduckgo, _search_bing, _search_ddgs_lib), query, max_results)


def news(query: str = "", max_results: int = 6) -> list[SearchResult]:
    return _first_that_answers((_news_google, _news_bing), query, max_results)
