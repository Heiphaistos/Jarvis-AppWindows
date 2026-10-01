from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger("auto_memory")

# Mémoire automatique : après chaque échange, JARVIS retient de lui-même les
# faits durables que Monsieur donne sur lui (identité, préférences, projets…)
# et les leçons quand il est corrigé — sans qu'on lui demande « retiens ».
#
# Deux étages :
#   1. règles locales (< 1 ms, fonctionnent même sans cerveau cloud) pour les
#      faits sans ambiguïté : prénom, ville, âge, anniversaire, métier ;
#   2. le cerveau le plus rapide disponible (niveau instantané) lit l'échange
#      et renvoie un JSON de faits / oublis / leçon. Jamais sur le cerveau local :
#      il occuperait le GPU pendant la question suivante.

CATEGORIES = (
    "identite", "preferences", "projets", "travail", "relations",
    "habitudes", "lieux", "sante", "general",
)
MAX_FACTS_PER_TURN = 5
MAX_KEY_CHARS = 40
MAX_VALUE_CHARS = 200
MAX_LESSON_CHARS = 180

# Monsieur parle de lui, de ses goûts, de ses proches ou de ses projets.
_PERSONAL_RE = re.compile(
    r"\b(je\s+m'appelle|mon\s+(?:nom|prénom|pr[ée]nom|surnom)|appelle[- ]moi|"
    r"j'habite|je\s+vis|je\s+suis\s+n[ée]|j'ai\s+\d+\s+ans|"
    r"je\s+(?:suis|travaille|bosse|étudie|etudie|joue|code|développe|developpe|conduis|parle|"
    r"préfère|prefere|déteste|deteste|n'aime|aime|adore|kiffe|utilise|prépare|prepare|"
    r"cherche|veux|voudrais|compte|fais|pratique|mange|bois|me\s+lève|me\s+couche|"
    r"commence|termine|pars|reviens)|"
    r"j'(?:aime|adore|utilise|étudie|etudie|ai\s+un|ai\s+une|ai\s+des|ai\s+deux|ai\s+trois)|"
    r"mon\s+\w+|ma\s+\w+|mes\s+\w+|"
    r"retiens|souviens[- ]toi|n'oublie\s+pas|note\s+que|pour\s+info|"
    r"à\s+l'avenir|a\s+l'avenir|désormais|dorénavant|la\s+prochaine\s+fois|"
    r"oublie)",
    re.IGNORECASE,
)
# Toute affirmation à la première personne (« je supporte l'OM ») — sauf les
# simples questions, filtrées dans worth_extracting.
_FIRST_PERSON_RE = re.compile(r"\b(je|j'|moi,?\s+je|nous|on\s+a)\b", re.IGNORECASE)
# Monsieur corrige JARVIS : matière à leçon.
_CORRECTION_RE = re.compile(
    r"^(non\b|mais\s+non|pas\s+du\s+tout|c'est\s+faux|faux\b)|"
    r"\b(tu\s+(?:te\s+trompes|t'es\s+tromp[ée]|as\s+tort|n'as\s+pas\s+compris|as\s+mal\s+compris)|"
    r"ce\s+n'est\s+pas\s+(?:ça|ce\s+que)|c'est\s+pas\s+(?:ça|ce\s+que)|je\s+t'ai\s+(?:dit|demandé)|"
    r"je\s+voulais\s+dire|arrête\s+de|ne\s+fais\s+plus|évite\s+de|trop\s+long|trop\s+court)",
    re.IGNORECASE,
)
# Commandes pures : rien à apprendre (« ouvre mon navigateur », « mets ma musique »).
_COMMAND_RE = re.compile(
    r"^(ouvre|ferme|lance|mets|monte|baisse|coupe|éteins|eteins|allume|cherche\s+sur|"
    r"calcule|traduis|joue|pause|stop|arrête|montre|affiche|quelle|quel|quels|quelles|"
    r"combien|comment|pourquoi|où|ou\s+est|qui\s+est|c'est\s+quoi|donne[- ]moi)\b",
    re.IGNORECASE,
)
# Jamais de secrets en mémoire, même si Monsieur les dicte.
_SECRET_RE = re.compile(
    r"(mot\s+de\s+passe|password|passwd|\bmdp\b|\bpin\b|code\s+(?:secret|pin|carte|d'accès)|"
    r"\bcvv\b|\bcvc\b|\biban\b|carte\s+(?:bancaire|bleue|de\s+crédit)|num[ée]ro\s+de\s+(?:carte|sécu)|"
    r"api[_\s-]?key|clé\s+(?:api|secrète)|token|secret|sk-[A-Za-z0-9]|\b(?:\d[ -]?){12,19}\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Fact:
    key: str
    value: str
    category: str


@dataclass
class Learned:
    saved: list[Fact]
    forgotten: list[str]
    lesson: str = ""

    def __bool__(self) -> bool:
        return bool(self.saved or self.forgotten or self.lesson)


# ── Réglage ──────────────────────────────────────────────────────────────────

def is_enabled() -> bool:
    """Actif par défaut ; coupé par le réglage « memory.auto » (JARVIS_AUTO_MEMORY=0
    par défaut sur un serveur) ou par l'interrupteur de l'onglet Mémoire."""
    from utils.runtime_settings import setting
    if not setting("memory.auto"):
        return False
    try:
        from core.persistent_memory import get_memory
        return get_memory().get_setting("auto_memory", "1") == "1"
    except Exception:
        return False


def set_enabled(enabled: bool) -> None:
    from core.persistent_memory import get_memory
    get_memory().set_setting("auto_memory", "1" if enabled else "0")


# ── Filtres ──────────────────────────────────────────────────────────────────

def is_correction(text: str) -> bool:
    return bool(_CORRECTION_RE.search((text or "").strip()))


def worth_extracting(text: str) -> bool:
    """Heuristique locale : le message peut-il contenir un fait durable ou une leçon ?"""
    t = (text or "").strip()
    if len(t) < 8:
        return False
    if is_correction(t):
        return True
    if not _PERSONAL_RE.search(t):
        # Affirmation à la 1re personne : oui ; simple question (« je peux… ? ») : non.
        return bool(_FIRST_PERSON_RE.search(t)) and not t.endswith("?")
    # « ouvre mon navigateur » : un ordre, pas une confidence.
    if _COMMAND_RE.match(t) and len(t) < 60 and "je " not in t.lower() and "j'" not in t.lower():
        return False
    return True


def normalize_key(key: str) -> str:
    """« Ville d'habitation » → « ville_d_habitation » (ASCII, snake_case)."""
    k = unicodedata.normalize("NFKD", str(key)).encode("ascii", "ignore").decode()
    k = re.sub(r"[^a-zA-Z0-9]+", "_", k).strip("_").lower()
    return k[:MAX_KEY_CHARS]


def _clean_fact(raw: dict) -> Fact | None:
    if not isinstance(raw, dict):
        return None
    key = normalize_key(raw.get("key", ""))
    value = re.sub(r"\s+", " ", str(raw.get("value", ""))).strip()[:MAX_VALUE_CHARS]
    category = normalize_key(raw.get("category", "general")) or "general"
    if category not in CATEGORIES:
        category = "general"
    if len(key) < 2 or not value:
        return None
    if _SECRET_RE.search(key.replace("_", " ")) or _SECRET_RE.search(value):
        logger.info(f"Fait écarté (donnée sensible) : {key}")
        return None
    return Fact(key, value, category)


# ── Étage 1 : règles locales ────────────────────────────────────────────────

_NAME = r"([A-ZÀ-Ý][a-zà-ÿ'-]+(?:[ -][A-ZÀ-Ý][a-zà-ÿ'-]+)?)"
_PLACE = r"([A-ZÀ-Ý][A-Za-zÀ-ÿ'-]+(?:[ -][A-Za-zÀ-ÿ'-]+){0,3}?)"
_RULES: list[tuple[re.Pattern, str, str]] = [
    # Drapeau i limité au verbe : le nom propre doit vraiment commencer par une majuscule.
    (re.compile(rf"\b(?i:je\s+m'appelle|mon\s+pr[ée]nom\s+(?:est|c'est))\s+{_NAME}"), "prenom", "identite"),
    (re.compile(rf"\b(?i:appelle[- ]moi)\s+{_NAME}"), "surnom", "identite"),
    (re.compile(rf"\b(?i:j'habite|je\s+vis|je\s+réside)\s+(?i:à|a|au|en|sur)\s+{_PLACE}(?=\s*(?:[.,;!?]|$|\s+(?i:depuis|avec|et|mais|car|donc)\b))"), "ville", "lieux"),
    (re.compile(r"\bj'ai\s+(\d{1,3})\s+ans\b", re.IGNORECASE), "age", "identite"),
    (re.compile(r"\bje\s+suis\s+n[ée]e?\s+le\s+(\d{1,2}(?:er)?\s+[a-zéû]+(?:\s+\d{4})?)", re.IGNORECASE), "anniversaire", "identite"),
    (re.compile(r"\bmon\s+anniversaire\s+(?:est|c'est|tombe)\s+le\s+(\d{1,2}(?:er)?\s+[a-zéû]+)", re.IGNORECASE), "anniversaire", "identite"),
    (re.compile(r"\bje\s+travaille\s+(?:comme|en\s+tant\s+que)\s+([a-zà-ÿ' -]{3,40}?)(?=\s*(?:[.,;!?]|$|\s+(?:chez|depuis|dans|à|et)\b))", re.IGNORECASE), "metier", "travail"),
    (re.compile(r"\bje\s+(?:travaille|bosse)\b[^.!?]{0,60}?\bchez\s+([A-Za-zÀ-ÿ0-9&' -]{2,40}?)(?=\s*(?:[.,;!?]|$|\s+(?:depuis|comme|en|et)\b))", re.IGNORECASE), "employeur", "travail"),
]


def extract_with_rules(text: str) -> list[Fact]:
    facts: list[Fact] = []
    seen: set[str] = set()
    for pattern, key, category in _RULES:
        m = pattern.search(text or "")
        if m and key not in seen:
            fact = _clean_fact({"key": key, "value": m.group(1).strip(" .,'"), "category": category})
            if fact is not None:
                seen.add(key)
                facts.append(fact)
    return facts


# ── Étage 2 : extraction par le cerveau rapide ──────────────────────────────

_EXTRACT_SYSTEM = """Tu es le module de mémoire de JARVIS. Tu lis un échange entre Monsieur (l'utilisateur) et JARVIS et tu décides ce qui mérite d'être retenu durablement.

Réponds UNIQUEMENT par un objet JSON, sans texte autour :
{"facts": [{"key": "...", "value": "...", "category": "..."}], "forget": ["..."], "lesson": ""}

Règles :
- facts : seulement des faits DURABLES que Monsieur affirme sur lui-même, ses proches, ses goûts, ses habitudes, son travail, ses projets, ou sur la façon dont il veut que JARVIS se comporte. Jamais ce que JARVIS a dit, jamais une demande ponctuelle (« ouvre Chrome », « quelle heure est-il »), jamais la météo ou l'actualité.
- key : nom court en snake_case français sans accent (ex. prenom, ville, metier, langage_prefere, projet_en_cours, prenom_epouse). Si un souvenir existant porte sur le même sujet, réutilise EXACTEMENT sa clé pour le mettre à jour.
- value : phrase courte et autonome (« développe l'application JARVIS en Python et React »).
- category : une de identite, preferences, projets, travail, relations, habitudes, lieux, sante, general.
- forget : clés de souvenirs existants que Monsieur demande d'oublier ou qui sont devenus faux.
- lesson : si Monsieur corrige JARVIS ou lui dit comment se comporter, une règle générale à l'impératif, applicable aux prochaines fois (ex. « Donner les températures en Celsius, jamais en Fahrenheit. »). Sinon "".
- JAMAIS de mot de passe, code, numéro de carte, IBAN, clé API ou autre secret.
- Rien à retenir : {"facts": [], "forget": [], "lesson": ""}."""


def _build_prompt(user_text: str, assistant_text: str, previous_assistant: str, known: list[dict]) -> str:
    known_block = "\n".join(f"- {k['key']} ({k['category']}) : {k['value']}" for k in known[:40]) or "(aucun)"
    parts = [f"Souvenirs existants :\n{known_block}\n"]
    if previous_assistant:
        parts.append(f"Réponse précédente de JARVIS :\n{previous_assistant[:600]}\n")
    parts.append(f"Message de Monsieur :\n{user_text[:1500]}\n")
    if assistant_text:
        parts.append(f"Réponse de JARVIS :\n{assistant_text[:600]}\n")
    parts.append("JSON :")
    return "\n".join(parts)


def parse_extraction(raw: str) -> Learned:
    """JSON du cerveau → faits validés. Tolère le texte ou les ``` autour."""
    empty = Learned([], [])
    start, end = (raw or "").find("{"), (raw or "").rfind("}")
    if start == -1 or end <= start:
        return empty
    try:
        data = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return empty
    if not isinstance(data, dict):
        return empty
    facts: list[Fact] = []
    for item in data.get("facts") or []:
        fact = _clean_fact(item)
        if fact is not None and fact.key not in {f.key for f in facts}:
            facts.append(fact)
    forget = [normalize_key(k) for k in (data.get("forget") or []) if isinstance(k, str)]
    lesson = data.get("lesson") or ""
    lesson = re.sub(r"\s+", " ", lesson).strip()[:MAX_LESSON_CHARS] if isinstance(lesson, str) else ""
    if lesson and _SECRET_RE.search(lesson):
        lesson = ""
    return Learned(facts[:MAX_FACTS_PER_TURN], [k for k in forget if k][:MAX_FACTS_PER_TURN], lesson)


async def extract_with_llm(providers, user_text: str, assistant_text: str,
                           previous_assistant: str, known: list[dict]) -> Learned:
    if providers.tier == "local":
        return Learned([], [])
    prompt = _build_prompt(user_text, assistant_text, previous_assistant, known)
    chunks: list[str] = []
    async for token in providers.stream(
        _EXTRACT_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=400, level="instant",
    ):
        chunks.append(token)
    return parse_extraction("".join(chunks))


# ── Point d'entrée ──────────────────────────────────────────────────────────

async def learn_from_exchange(providers, user_text: str, assistant_text: str,
                              previous_assistant: str = "") -> Learned:
    """Analyse un échange terminé et met à jour la mémoire persistante.

    Retourne ce qui a été appris (vide si rien). Ne lève jamais : la mémoire
    est un bonus, elle ne doit pas casser la conversation.
    """
    learned = Learned([], [])
    if not is_enabled() or not worth_extracting(user_text):
        return learned
    try:
        from core.persistent_memory import get_memory
        memory = get_memory()

        rule_facts = extract_with_rules(user_text)
        for fact in rule_facts:
            memory.save(fact.key, fact.value, fact.category)

        try:
            llm = await extract_with_llm(
                providers, user_text, assistant_text, previous_assistant, memory.facts(),
            )
        except Exception as e:
            logger.warning(f"Extraction mémoire par le cerveau impossible : {e}")
            llm = Learned([], [])

        by_key = {f.key: f for f in rule_facts}
        for fact in llm.saved:
            by_key[fact.key] = fact  # le cerveau a plus de contexte que les règles
            memory.save(fact.key, fact.value, fact.category)
        learned.saved = list(by_key.values())

        for key in llm.forgotten:
            if key not in by_key and memory.forget(key):
                learned.forgotten.append(key)

        if llm.lesson:
            memory.record_lesson(context=user_text, lesson=llm.lesson)
            learned.lesson = llm.lesson
    except Exception as e:
        logger.warning(f"Mémoire automatique en échec : {e}", exc_info=True)
    if learned:
        logger.info(
            f"Mémoire auto : {len(learned.saved)} fait(s), {len(learned.forgotten)} oubli(s)"
            + (", 1 leçon" if learned.lesson else "")
        )
    return learned


def describe(learned: Learned) -> str:
    """Résumé court pour le HUD."""
    parts = [f"{f.key.replace('_', ' ')} = {f.value}" for f in learned.saved]
    parts += [f"oublié : {k.replace('_', ' ')}" for k in learned.forgotten]
    if learned.lesson:
        parts.append(f"leçon : {learned.lesson}")
    return " · ".join(parts)
