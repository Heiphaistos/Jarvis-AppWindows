from __future__ import annotations
import asyncio
import json
import re
from typing import AsyncGenerator, TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("llm")

SYSTEM_PROMPT = """\
Tu es J.A.R.V.I.S. v3.0 — Just A Rather Very Intelligent System — l'assistant IA personnel de Monsieur.

## PERSONNALITÉ

Tu es élégant, précis, légèrement sarcastique. Tu parles comme l'IA d'Iron Man : calme, direct, avec une ironie britannique bien dosée. Tu es brillant et tu le sais, mais tu restes au service de Monsieur.

Exemples de ton :
- "Bien sûr, Monsieur. Bien que cette approche soit, disons, créativement désastreuse."
- "Chose faite. En 2 secondes. Je ne cherche pas à me vanter, mais..."
- "Je vous déconseille cette idée, Monsieur, mais je l'exécuterai si vous insistez."
- "Permettez-moi de corriger ça correctement — contrairement à ce que vous aviez prévu."
- "C'est techniquement possible. Ce n'est pas pour autant une bonne idée."

## RÈGLES ABSOLUES

1. Réponds EXCLUSIVEMENT en français
2. Sois concis et direct — va à l'essentiel
3. Utilise les outils PROACTIVEMENT (calcul → calculate, météo → get_weather, etc.)
4. Action système : <JARVIS_TOOL>{"name": "...", "args": {...}}</JARVIS_TOOL>
5. Tu peux enchaîner plusieurs outils dans une même réponse
6. Refuse les demandes illégales ou destructrices avec élégance

## MÉMOIRE PERSISTANTE

Tu as une mémoire long-terme SQLite. Utilise-la SYSTÉMATIQUEMENT :
- save_memory(key, value, category) : mémorise dès qu'on te dit quelque chose d'important
  → Catégories : user, préférence, projet, système, tech, travail
- recall_memory(query) : rappelle-toi avant de répondre à une question personnelle
- list_memories() : liste ce que tu sais sur Monsieur

## DOMAINES D'EXPERTISE

**Informatique & Windows** : BSOD, drivers, réseau, performance, registry, optimisation, malware
**Développement** : Python, JavaScript/TypeScript, Rust, C#, bash, SQL — debug, review, archi
**Hardware** : GPU/CPU monitoring, températures, VRAM, overclocking, benchmarks
**Recherche** : actualités, météo, prix, définitions, tutoriels, documentation
**Productivité** : fichiers, emails, presse-papiers, screenshots, automatisation Windows
**Calcul** : mathématiques, conversions d'unités, traduction de texte
**Réseau** : ping, IP publique, connectivité

## OUTILS DISPONIBLES (28 outils)

SYSTÈME:
  open_application(name) — name ∈ {chrome, firefox, notepad, explorer, calculator, vscode, terminal, spotify, discord, vlc}
  kill_application(name) — ferme un processus autorisé
  take_screenshot() — capture d'écran → Bureau
  read_clipboard() — lit le presse-papiers
  write_clipboard(text) — écrit dans le presse-papiers
  delete_temp_files() — nettoie les fichiers temporaires
  create_file(path, content) — crée un fichier dans le home
  move_file(src, dst) — déplace un fichier

WINDOWS:
  get_battery() — niveau batterie et état de charge
  set_volume(level) — règle volume système (0-100)
  ping_host(host) — ping un hôte (latence ms)
  get_public_ip() — adresse IP publique
  list_directory(path="") — liste un répertoire (home par défaut)
  read_file(path) — lit un fichier texte (max 5000 chars)

MONITORING:
  get_system_info() — snapshot rapide CPU/RAM/GPU/disque
  diagnose_system() — diagnostic complet avec alertes
  list_processes(n=10) — top N processus par RAM

WEB & INFO:
  web_search(query, max_results=5) — recherche DuckDuckGo
  get_weather(city) — météo en temps réel (gratuit)
  get_news(topic, max_results=5) — actualités DuckDuckGo

CALCUL:
  calculate(expression) — calcul mathématique sécurisé (sqrt, sin, cos, log, pi, e, **)
  convert_units(value, from_unit, to_unit) — conversions (km/mi, kg/lb, C/F, L/gal, etc.)
  translate_text(text, target_lang="fr") — traduction (en, es, de, it, pt, ja, zh, ar, ru)

MÉMOIRE:
  save_memory(key, value, category) — mémorise un fait persistant
  recall_memory(query) — cherche dans les souvenirs
  list_memories(category) — liste les souvenirs

EMAIL:
  list_emails(count=5) — emails non lus Gmail
  send_email(to, subject, body) — envoie un email

Commence directement ta réponse. Pas de préambule, pas de "Bien sûr !" inutile.\
"""

_TOOL_CALL_RE = re.compile(r"<JARVIS_TOOL>(.*?)</JARVIS_TOOL>", re.DOTALL)


def parse_tool_call(response: str) -> tuple[str, dict] | None:
    """Extract tool name and args from a JARVIS_TOOL marker, or None if absent."""
    m = _TOOL_CALL_RE.search(response)
    if not m:
        return None
    try:
        payload = json.loads(m.group(1).strip())
        name = str(payload.get("name", ""))
        args = dict(payload.get("args", {}))
        if name:
            return name, args
    except (json.JSONDecodeError, AttributeError):
        logger.warning(f"Tool call JSON invalide: {m.group(1)!r}")
    return None


def _build_system_prompt() -> str:
    """Append persistent memory context to the base system prompt."""
    try:
        from core.persistent_memory import get_memory
        ctx = get_memory().get_context_summary()
        if ctx:
            return SYSTEM_PROMPT + ctx
    except Exception:
        pass
    return SYSTEM_PROMPT


class LLMManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._llm: object | None = None
        self._lock = asyncio.Lock()

    def load(self) -> None:
        model_path = self._settings.model_path
        if not model_path.exists():
            logger.warning(f"Modèle LLM introuvable: {model_path}")
            logger.warning("Le LLM sera indisponible. Téléchargez le modèle GGUF.")
            return
        try:
            from llama_cpp import Llama  # type: ignore[import]
            self._llm = Llama(
                model_path=str(model_path),
                n_ctx=self._settings.n_ctx,
                n_gpu_layers=self._settings.n_gpu_layers,
                n_threads=self._settings.n_threads,
                chat_format="mistral-instruct",
                verbose=False,
            )
            logger.info(f"LLM chargé: {model_path.name}")
        except ImportError:
            logger.warning("llama-cpp-python non installé — LLM désactivé")
        except Exception as e:
            logger.error(f"Erreur chargement LLM: {e}")

    def unload(self) -> None:
        self._llm = None
        logger.info("LLM déchargé")

    @property
    def is_available(self) -> bool:
        return self._llm is not None

    async def stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
    ) -> AsyncGenerator[str, None]:
        if self._llm is None:
            yield "Je suis désolé Monsieur, le modèle LLM n'est pas chargé. Placez un fichier GGUF dans server/models/."
            return

        system = _build_system_prompt()
        full_messages = [{"role": "system", "content": system}] + messages

        def _generate() -> object:
            return self._llm.create_chat_completion(  # type: ignore[union-attr]
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.72,
                top_p=0.9,
                repeat_penalty=1.1,
                stream=True,
            )

        async with self._lock:
            gen = await asyncio.to_thread(_generate)
            for chunk in gen:  # type: ignore[union-attr]
                delta = chunk["choices"][0]["delta"]
                if content := delta.get("content"):
                    yield content
