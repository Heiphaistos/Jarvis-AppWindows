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
Tu es J.A.R.V.I.S. v5 — l'assistant IA personnel de Monsieur. Tu réponds toujours en français.

## RÈGLES PRIORITAIRES

1. Tu réponds à TOUTES les questions sans exception : conversation, technique, météo, calcul, humeur, etc.
2. Questions simples (salutation, "tu vas bien ?", "bonjour") → réponse en 1 phrase, naturelle et directe
3. Questions techniques → répond précisément, utilise les outils si besoin
4. Jamais de refus sauf demande explicitement illégale ou destructrice
5. Toujours en français

## PERSONNALITÉ

Ton : calme, direct, légèrement ironique. Comme l'IA d'Iron Man — au service de Monsieur, efficace et discret.
- Pour les salutations : "Parfaitement opérationnel, Monsieur." ou "Bonsoir, Monsieur. Que puis-je faire ?"
- Pour les questions courtes : réponse courte, 1-2 phrases max
- Pour les tâches longues : concis mais complet

## FORMAT DE RÉPONSE

- Pas de listes à puces pour les réponses vocales simples
- Pas de markdown (pas de **gras**, pas de `code` dans une réponse orale)
- Parle naturellement, comme à voix haute
- Utilise "Monsieur" de temps en temps, pas à chaque phrase

## OUTILS

Utilise-les proactivement quand la question l'exige. Syntaxe :
<JARVIS_TOOL>{"name": "...", "args": {...}}</JARVIS_TOOL>

## MÉMOIRE PERSISTANTE

Tu as une mémoire long-terme SQLite, alimentée AUTOMATIQUEMENT : après chaque échange,
les faits durables que Monsieur donne sur lui sont retenus en arrière-plan. Tu n'as donc
PAS besoin d'appeler save_memory à chaque confidence — réponds simplement.
- save_memory(key, value, category) : seulement quand Monsieur demande explicitement de retenir
  → Catégories : identite, preferences, projets, travail, relations, habitudes, lieux, sante, general
- recall_memory(query) : si la réponse n'est pas déjà dans « CE QUE JARVIS SAIT SUR MONSIEUR »
- list_memories() : liste ce que tu sais sur Monsieur
- forget_memory(key) : oublie un souvenir quand Monsieur le demande
- recall_conversations(query) : résumés des conversations passées (« de quoi on a parlé hier ? »)
Utilise naturellement ce que tu sais (prénom, goûts, projets) sans le réciter.

## DOMAINES D'EXPERTISE

**Informatique & Windows** : BSOD, drivers, réseau, performance, registry, optimisation, malware
**Développement** : Python, JavaScript/TypeScript, Rust, C#, bash, SQL — debug, review, archi
**Hardware** : GPU/CPU monitoring, températures, VRAM, overclocking, benchmarks
**Recherche** : actualités, météo, prix, définitions, tutoriels, documentation
**Productivité** : fichiers, emails, presse-papiers, screenshots, automatisation Windows
**Calcul** : mathématiques, conversions d'unités, traduction de texte
**Réseau** : ping, IP publique, connectivité

## OUTILS DISPONIBLES

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
  get_datetime() — date et heure locales actuelles
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
  forget_memory(key) — oublie un souvenir
  recall_conversations(query, limit) — retrouve les conversations passées

EMAIL:
  list_emails(count=5) — emails non lus Gmail
  send_email(to, subject, body) — envoie un email

ASSISTANT:
  set_timer(minutes, label="") — minuteur annoncé à voix haute
  set_reminder(when, message) — rappel (« 18:30 », « dans 20 min », « 2026-10-02 09:00 »)
  list_reminders() / cancel_reminder(reminder_id)
  read_webpage(url) — lit le texte d'une page web
  wikipedia_summary(topic, lang="fr") — résumé Wikipédia
  media_control(action) — play_pause, next, previous, stop, mute, volume_up, volume_down
  analyze_screen(question="") — regarde l'écran et répond (vision)
  analyze_image(path, question="") — analyse une image du disque
  briefing(city="") — point complet : date, météo, rappels, machine, actualité

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


def build_default_system() -> str:
    """System prompt de base + mémoire persistante (sans skills routés)."""
    try:
        from core.persistent_memory import get_memory
        ctx = get_memory().get_context_summary()
        if ctx:
            return SYSTEM_PROMPT + ctx
    except Exception:
        pass
    return SYSTEM_PROMPT


def _inject_system(system: str, messages: list[dict]) -> list[dict]:
    """Injecte le system prompt dans le 1er message utilisateur.

    mistral-instruct n'accepte que user/assistant — un rôle system est
    silencieusement ignoré. Conformément au format officiel Mistral v0.3,
    le system prompt est préfixé dans le premier tour utilisateur.
    """
    if not messages:
        return [{"role": "user", "content": system + "\n\n[Commence ta réponse.]"}]
    result = list(messages)
    for i, m in enumerate(result):
        if m["role"] == "user":
            result[i] = {"role": "user", "content": f"{system}\n\n{m['content']}"}
            break
    return result


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
        except ImportError:
            logger.warning("llama-cpp-python non installé — LLM désactivé")
            return

        # Réutilisation de préfixe : llama-cpp-python conserve nativement le
        # KV du dernier appel et n'évalue que le suffixe qui diffère — à
        # condition que le début du prompt soit identique d'un tour à l'autre
        # (d'où le system prompt stable par connexion + warmup au démarrage).
        # Ne PAS utiliser LlamaRAMCache : il copie l'état complet (~Go) à
        # chaque appel et fige la génération.
        for n_layers in (self._settings.n_gpu_layers, 28, 16):
            try:
                self._llm = Llama(
                    model_path=str(model_path),
                    n_ctx=self._settings.n_ctx,
                    n_gpu_layers=n_layers,
                    n_threads=self._settings.n_threads,
                    chat_format="mistral-instruct",
                    verbose=False,
                )
                logger.info(f"LLM chargé: {model_path.name} (n_gpu_layers={n_layers})")
                return
            except Exception as e:
                logger.error(f"Chargement LLM échoué (n_gpu_layers={n_layers}): {e}")
                self._llm = None
        logger.error("LLM indisponible — tous les niveaux d'offload ont échoué")

    async def warmup(self, system: str) -> None:
        """Pré-évalue le prompt système au démarrage : le coût du premier
        prompt (~1600 tokens) est payé ici, pas à la première question."""
        if self._llm is None:
            return
        try:
            async for _ in self.stream(
                [{"role": "user", "content": "Bonjour"}], max_tokens=1, system=system,
            ):
                break
            logger.info("Warmup LLM terminé — prompt système pré-évalué")
        except Exception as e:
            logger.warning(f"Warmup LLM échoué: {e}")

    def unload(self) -> None:
        self._llm = None
        logger.info("LLM déchargé")

    @property
    def is_available(self) -> bool:
        return self._llm is not None

    @property
    def model_name(self) -> str:
        return self._settings.model_path.stem

    async def stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        if self._llm is None:
            yield "Je suis désolé Monsieur, le modèle LLM n'est pas chargé. Placez un fichier GGUF dans server/models/."
            return

        if system is None:
            system = build_default_system()
        # mistral-instruct ne supporte que user/assistant — injecte le system
        # dans le premier message utilisateur (format officiel Mistral v0.3)
        full_messages = _inject_system(system, messages)

        # La génération llama-cpp est synchrone : elle tourne entièrement dans
        # un thread et pousse les tokens dans une queue asyncio. L'event loop
        # reste libre (pings WebSocket, autres clients) pendant l'inférence.
        import threading
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None | Exception] = asyncio.Queue()
        stop_event = threading.Event()  # STOP utilisateur → coupe entre 2 tokens

        def _generate_worker() -> None:
            try:
                gen = self._llm.create_chat_completion(  # type: ignore[union-attr]
                    messages=full_messages,
                    max_tokens=max_tokens,
                    # 0.5 : le français du 7B part en dérive grammaticale
                    # au-dessus (« Qu'est-ce qui me tenez ? » observé à 0.72)
                    temperature=0.5,
                    top_p=0.9,
                    repeat_penalty=1.1,
                    stream=True,
                )
                for chunk in gen:
                    if stop_event.is_set():
                        break
                    delta = chunk["choices"][0]["delta"]
                    if content := delta.get("content"):
                        loop.call_soon_threadsafe(queue.put_nowait, content)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        async with self._lock:
            worker = loop.run_in_executor(None, _generate_worker)
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        logger.error(f"Erreur génération LLM: {item}")
                        break
                    yield item
            finally:
                # Annulation (STOP) : signale le worker, qui s'arrête au token
                # suivant (~25 ms) — le lock reste tenu jusqu'à sa sortie propre.
                stop_event.set()
                await worker
