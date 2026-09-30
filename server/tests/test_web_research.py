import pytest

import core.web_search as ws
import tools.web_tools as wt
from core.intent import fast_route
from core.providers.router import classify
from core.web_search import SearchResult

DDG_PAGE = """
<div class="serp__results">
 <div class="result results_links results_links_deep result--ad">
  <a rel="nofollow" class="result__a" href="https://duckduckgo.com/y.js?ad_domain=pub.com&amp;u3=x">Publicité</a>
 </div>
 <div class="result results_links results_links_deep web-result ">
  <h2 class="result__title">
   <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ffr.wikipedia.org%2Fwiki%2FITER&amp;rut=abc">ITER — <b>Wikipédia</b></a>
  </h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">ITER est un projet de <b>réacteur</b> à fusion nucléaire.</a>
 </div>
 <div class="result results_links results_links_deep web-result ">
  <h2 class="result__title">
   <a rel="nofollow" class="result__a" href="https://www.iter.org/fr/proj">Le projet ITER</a>
  </h2>
  <a class="result__snippet" href="https://www.iter.org/fr/proj">Site officiel &amp; calendrier.</a>
 </div>
</div>
"""

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google News</title>
 <item>
  <title>La NASA lance Artemis III - Le Monde</title>
  <link>https://news.google.com/rss/articles/abc</link>
  <pubDate>Tue, 29 Sep 2026 08:00:00 GMT</pubDate>
  <description>&lt;a href="x"&gt;La NASA lance Artemis III&lt;/a&gt; vers la Lune</description>
  <source url="https://www.lemonde.fr">Le Monde</source>
 </item>
 <item><title>Sans lien</title></item>
</channel></rss>"""


def test_parse_duckduckgo():
    results = ws.parse_duckduckgo(DDG_PAGE)
    assert [r.url for r in results] == ["https://fr.wikipedia.org/wiki/ITER", "https://www.iter.org/fr/proj"]
    assert results[0].title == "ITER — Wikipédia"
    assert results[0].snippet == "ITER est un projet de réacteur à fusion nucléaire."
    assert results[1].snippet == "Site officiel & calendrier."


def test_parse_rss_google_news():
    [r] = ws.parse_rss(RSS)
    assert r.title == "La NASA lance Artemis III"
    assert r.source == "Le Monde" and r.date == "2026-09-29"
    assert r.snippet == "La NASA lance Artemis III vers la Lune"
    assert ws.parse_rss("<html>pas du rss") == []


def test_moteur_suivant_si_le_premier_tombe(monkeypatch):
    def down(q):
        raise OSError("bloqué")

    def empty(q):
        return []

    def bing(q):
        return [SearchResult("A", "https://a.fr", "x"), SearchResult("A bis", "https://a.fr", "y"),
                SearchResult("B", "https://b.fr", "z")]

    monkeypatch.setattr(ws, "_search_duckduckgo", down)
    monkeypatch.setattr(ws, "_search_bing", empty)
    monkeypatch.setattr(ws, "_search_ddgs_lib", bing)
    assert [r.url for r in ws.search("q")] == ["https://a.fr", "https://b.fr"]  # doublon retiré


def test_tous_les_moteurs_hors_ligne(monkeypatch):
    def down(q):
        raise OSError("hors ligne")

    for name in ("_search_duckduckgo", "_search_bing", "_search_ddgs_lib"):
        monkeypatch.setattr(ws, name, down)
    with pytest.raises(ConnectionError):
        ws.search("q")
    assert wt.web_search("q").startswith("Erreur recherche")


def test_web_search_et_actualites(monkeypatch):
    monkeypatch.setattr(ws, "_search_duckduckgo", lambda q: ws.parse_duckduckgo(DDG_PAGE))
    out = wt.web_search("ITER", 5)
    assert "ITER — Wikipédia" in out and "https://www.iter.org/fr/proj" in out

    from tools.info_tools import get_news
    monkeypatch.setattr(ws, "_news_google", lambda q: ws.parse_rss(RSS))
    news = get_news("nasa")
    assert "La NASA lance Artemis III" in news and "Le Monde · 2026-09-29" in news


def test_meilleurs_passages():
    text = "\n".join([
        "Menu Accueil Contact Abonnez-vous à notre newsletter pour ne rien manquer.",
        "Le chat est un animal domestique très apprécié dans les foyers français.",
        "Le réacteur ITER vise à démontrer la fusion nucléaire à grande échelle en 2035.",
        "Politique de cookies : nous utilisons des traceurs pour mesurer l'audience.",
    ])
    out = wt.best_passages(text, "Quand ITER produira-t-il la fusion ?", budget=120)
    assert out.startswith("Le réacteur ITER")
    assert "cookies" not in out


def test_deep_research(monkeypatch):
    results = [
        SearchResult("ITER — Wikipédia", "https://fr.wikipedia.org/wiki/ITER", "extrait wiki"),
        SearchResult("ITER encore", "https://fr.wikipedia.org/wiki/Tokamak", "même site"),
        SearchResult("Le projet ITER", "https://www.iter.org/proj", "officiel"),
        SearchResult("Blog", "https://blog.exemple.fr/iter", "blog illisible"),
    ]
    monkeypatch.setattr(ws, "search", lambda q, n=8: results)
    pages = {
        "https://fr.wikipedia.org/wiki/ITER": "ITER\n\nLe premier plasma d'ITER est prévu en 2035 selon le calendrier révisé.",
        "https://www.iter.org/proj": "Projet\n\nITER réunit 35 pays autour de la fusion nucléaire depuis 2006.",
    }

    def fetch(url):
        if url not in pages:
            raise ValueError("Lecture impossible")
        return url, pages[url]

    monkeypatch.setattr(wt, "_fetch", fetch)
    out = wt.deep_research("Où en est ITER ?", max_sources=3)
    assert "(3 sources)" in out
    assert "[1] ITER — Wikipédia" in out and "prévu en 2035" in out
    assert "Tokamak" not in out  # un seul lien par site
    assert "[2] Le projet ITER" in out and "35 pays" in out
    assert "[3] Blog" in out and "extrait du moteur" in out  # page illisible → extrait
    assert "cite-les avec [n]" in out


@pytest.mark.parametrize("text,question", [
    ("fais une recherche sur les meilleures cartes graphiques 2026", "les meilleures cartes graphiques 2026"),
    ("Jarvis, renseigne-toi sur la fusion nucléaire", "la fusion nucléaire"),
    ("recherche approfondie sur le prix du bitcoin ?", "le prix du bitcoin"),
])
def test_intention_recherche(text, question):
    assert fast_route(text) == ("deep_research", {"question": question})


def test_niveau_profond():
    assert classify("recherche approfondie sur le télétravail") == "deep"


def test_suivi_outil_riche():
    from api.websocket import _tool_followup
    assert "une ou deux phrases" in _tool_followup("get_weather", {}, "12°C")
    rich = _tool_followup("deep_research", None, "DOSSIER")
    assert "structurée" in rich and "[n]" in rich and "une ou deux phrases" not in rich
