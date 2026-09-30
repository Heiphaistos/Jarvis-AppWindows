from __future__ import annotations
import re

from utils.logger import get_logger

logger = get_logger("intent")

# Routeur d'intention rapide : pour les demandes évidentes, l'outil est exécuté
# de façon déterministe AVANT le LLM (qui ne fait que formuler la réponse).
# Volontairement conservateur — au moindre doute, on laisse la boucle agent
# décider. Corrige les ratés d'appel d'outil du 7B local sur les formulations
# naturelles (« combien font 391 divisé par 17 ? »).

_WORD_OPS = [
    (re.compile(r"\bdivisés?\s+par\b", re.IGNORECASE), "/"),
    (re.compile(r"\bmultipliés?\s+par\b", re.IGNORECASE), "*"),
    (re.compile(r"\bfois\b", re.IGNORECASE), "*"),
    (re.compile(r"\bplus\b", re.IGNORECASE), "+"),
    (re.compile(r"\bmoins\b", re.IGNORECASE), "-"),
    (re.compile(r"\bpuissance\b", re.IGNORECASE), "**"),
    (re.compile(r"\bmodulo\b", re.IGNORECASE), "%"),
]
_CALC_PREFIX = re.compile(
    r"^(?:calcule[rz]?|combien\s+f(?:ont|ait)|résous|quel\s+est\s+le\s+résultat\s+d[e']?)\s*[:,]?\s*",
    re.IGNORECASE,
)
_CALC_ALLOWED = re.compile(r"^[\d\s+\-*/().,%^x×÷]+$")

_WEATHER_RE = re.compile(
    r"(?:météo|quel\s+temps(?:\s+fait-il)?)\s+(?:à|a|au|en|sur|pour|de)\s+"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{1,40}?)\s*\??$",
    re.IGNORECASE,
)
_TIME_RE = re.compile(
    r"quelle\s+heure|quel\s+jour\s+(?:on\s+est|sommes[- ]nous|est[- ]on)"
    r"|on\s+est\s+quel\s+jour|date\s+d['e] ?aujourd'hui|quelle\s+est\s+la\s+date",
    re.IGNORECASE,
)
_BATTERY_RE = re.compile(r"\bbatterie\b", re.IGNORECASE)
_BRIEFING_RE = re.compile(
    r"\b(briefing|fais[- ]moi (le|un) (point|topo|résumé)|quoi de neuf|récap(itulatif)? du jour|point du (jour|matin))\b",
    re.IGNORECASE,
)
_CONVERSATIONS_RE = re.compile(
    r"de\s+quoi\s+(?:on\s+(?:a|avait)|avons[- ]nous|nous\s+avons)\s+parl[ée]|"
    r"on\s+(?:a|avait)\s+parl[ée]\s+de\s+quoi|"
    r"(?:notre|la)\s+(?:dernière|précédente|derniere|precedente)\s+(?:conversation|discussion)",
    re.IGNORECASE,
)
_RESEARCH_RE = re.compile(
    r"^(?:jarvis[, ]+)?(?:fais(?:[- ]moi)?\s+une\s+recherche(?:\s+approfondie)?|recherche\s+approfondie|"
    r"renseigne[- ]toi|documente[- ]toi|creuse(?:\s+le\s+sujet)?|enquête)"
    r"\s+(?:sur|à\s+propos\s+d[e']|au\s+sujet\s+d[e']|concernant)?\s*(.{3,})$",
    re.IGNORECASE,
)
_IP_RE = re.compile(r"\bip\s+publique\b|\bmon\s+ip\b", re.IGNORECASE)


def _extract_calc(text: str) -> str | None:
    stripped = _CALC_PREFIX.sub("", text.strip())
    if stripped == text.strip() and not _CALC_ALLOWED.match(stripped.rstrip("?").strip()):
        # Pas de préfixe calcul et pas une expression pure → pas un calcul
        return None
    expr = stripped.rstrip("?!. ").strip()
    for pattern, op in _WORD_OPS:
        expr = pattern.sub(op, expr)
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    expr = re.sub(r"(?<=\d)x(?=\d)", "*", expr)  # 17x23 → 17*23
    expr = expr.replace(",", ".")
    expr = re.sub(r"\s+", "", expr)
    if not expr or not _CALC_ALLOWED.match(expr):
        return None
    if not re.search(r"\d", expr) or not re.search(r"[+\-*/%]", expr):
        return None
    return expr


def fast_route(text: str) -> tuple[str, dict] | None:
    """Retourne (tool_name, args) si l'intention est évidente, sinon None."""
    text = text.strip()

    # Recherche explicite : passe avant la borne de longueur (la question peut être longue).
    m = _RESEARCH_RE.search(text)
    if m and len(text) <= 400:
        return "deep_research", {"question": m.group(1).strip(" ?.!")}
    if len(text) > 120:
        return None  # phrase longue → contexte riche, laisser l'agent décider

    expr = _extract_calc(text)
    if expr:
        return "calculate", {"expression": expr}

    m = _WEATHER_RE.search(text)
    if m:
        return "get_weather", {"city": m.group(1).strip()}

    if _TIME_RE.search(text):
        return "get_datetime", {}

    if _BATTERY_RE.search(text) and re.search(
        r"niveau|combien|reste|état|charge|\?", text, re.IGNORECASE
    ):
        return "get_battery", {}

    if _IP_RE.search(text):
        return "get_public_ip", {}

    if _BRIEFING_RE.search(text):
        return "briefing", {}

    if _CONVERSATIONS_RE.search(text):
        return "recall_conversations", {"query": ""}

    return None
