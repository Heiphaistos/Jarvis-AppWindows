from __future__ import annotations
import asyncio
import json
import re
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import get_logger
from utils.runtime_settings import setting
from utils.config import MODELS_DIR
from core.llm import parse_tool_calls, _TOOL_CALL_RE
from core.memory import ContextMemory
from core.prompt import build_system_prompt
from core.providers import ProviderManager
from core.stt import STTManager
from core.tts import TTSManager
from tools.registry import ToolRegistry

from utils.rate_limiter import RateLimiter

_rate_limiter = RateLimiter()

logger = get_logger("websocket")

# Fin de parole par détection de silence, mesurée en durée (et non en nombre
# de morceaux : leur taille varie selon le micro et la fréquence d'échantillonnage).
# Seuil, délai de silence et durée maximale se règlent dans Paramètres › Voix.
SPEECH_CONFIRM_S = 0.15     # parole continue avant de la confirmer (anti-clic)
PRE_ROLL_S = 0.6            # audio gardé avant la parole — 1er mot jamais tronqué
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024   # 2 MB — audio chunk upper bound
MAX_TEXT_CHARS = 2000
ALLOWED_ORIGINS = {
    "http://localhost:1420",    # dev Vite
    "http://127.0.0.1:1420",    # dev Vite alt
    "tauri://localhost",         # Tauri v1 production
    "http://tauri.localhost",    # Tauri v2 production (WebView2)
    "https://tauri.localhost",   # Tauri v2 HTTPS variant
}

_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?…»!?"])\s+|(?<=\.\.\.)\s+')

MAX_AGENT_ITERATIONS = 5

# Outils qui renvoient un dossier à synthétiser (et non un résultat court à
# reformuler) : la réponse qui suit a besoin d'un vrai cerveau et de place.
RICH_TOOLS = {"deep_research", "read_webpage", "pc_diagnostic", "pc_health_report"}
_RICH_MAX_TOKENS = 1536
_LENGTH_FACTOR = {"short": 0.5, "normal": 1.0, "long": 2.0}


def _tool_followup(name: str, args: dict | None, result: str, chain: bool = False) -> str:
    """Message qui réinjecte le résultat d'un outil dans la conversation.

    chain : le cerveau peut enchaîner sur un autre outil si la demande a
    plusieurs étapes (« regarde la météo et mets un rappel s'il pleut »).
    Désactivé en local (le 7B boucle) et au dernier tour de la boucle.
    """
    header = f"[RÉSULTAT OUTIL {name}({args})]" if args is not None else f"[RÉSULTAT OUTIL {name}]"
    if name in RICH_TOOLS:
        return (
            f"{header}\n{result}\n\n"
            "Réponds maintenant à Monsieur en français à partir de ce contenu : réponse complète "
            "et structurée (titres courts ou puces si utile), faits précis, sources citées [n] "
            "quand elles sont numérotées, contradictions et incertitudes signalées. N'émets une "
            "nouvelle balise JARVIS_TOOL que si une information indispensable manque vraiment."
        )
    if chain:
        return (
            f"{header}\n{result}\n\n"
            "Si la demande de Monsieur comporte encore une étape (autre action ou information "
            "nécessaire), émets maintenant la balise JARVIS_TOOL de l'outil suivant, sans texte "
            "autour. Sinon, réponds directement en français, en une ou deux phrases, en rendant "
            "compte de tout ce qui a été fait. Ne rappelle jamais un outil déjà exécuté avec les "
            "mêmes arguments."
        )
    return (
        f"{header}\n{result}\n\n"
        "Réponds directement à Monsieur en français, en une ou deux phrases, à partir de ce "
        "résultat. N'émets PAS de balise JARVIS_TOOL — le résultat est déjà là."
    )


def _tools_followup(calls: list[tuple[str, dict]], results: list[str], chain: bool = False) -> str:
    """Résultats de plusieurs outils exécutés en parallèle, en un seul message."""
    blocks = "\n\n".join(
        f"[RÉSULTAT OUTIL {name}({args})]\n{result}" for (name, args), result in zip(calls, results)
    )
    # Consigne du plus exigeant : un dossier à synthétiser l'emporte sur une reformulation.
    rich = next((n for n, _ in calls if n in RICH_TOOLS), None)
    instruction = _tool_followup(rich or calls[0][0], None, "", chain=chain).split("\n\n", 1)[1]
    return f"{blocks}\n\n{instruction.replace('ce résultat', 'ces résultats')}"


def _call_key(name: str, args: dict) -> str:
    return f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)}"


async def _agent_loop(
    ws: "WebSocket",
    providers: "ProviderManager",
    tts: "TTSManager",
    tools: "ToolRegistry",
    messages: list[dict],
    tts_enabled: bool,
    message_id: str,
    tts_queue: "asyncio.Queue[str]",
    system: str,
    preexecuted: tuple[str, dict, str] | None = None,
    level: str = "standard",
) -> str:
    """Boucle agent : LLM → tool → LLM → ... → réponse finale (max 5 itérations)."""
    accumulated = ""
    if providers.tier == "local":
        from utils.perf import active_profile
        max_tokens = active_profile().max_tokens
    else:
        from core.providers.router import MAX_TOKENS
        max_tokens = MAX_TOKENS.get(level, 1024)
    # Longueur choisie dans les paramètres (Comportement)
    max_tokens = int(max_tokens * _LENGTH_FACTOR.get(str(setting("assistant.response_length")), 1.0))
    used_tools = False
    first_spoken = False  # 1re phrase déjà envoyée à la synthèse vocale
    lesson_recorded = False
    user_query = next(
        (m["content"][:200] for m in reversed(messages) if m["role"] == "user"), ""
    )

    async def _notify_route(provider, ttft: float, lvl: str) -> None:
        # Le HUD affiche quel cerveau a répondu, à quel niveau et en combien de temps.
        await manager.send(ws, "brain", {
            "messageId": message_id, "level": lvl, "provider": provider.name,
            "label": provider.label, "model": provider.model, "ttftMs": round(ttft * 1000),
        })

    async def _notify_fallback(label: str) -> None:
        await manager.send(ws, "notice", {
            "message": f"{label} indisponible — bascule sur le cerveau local.",
        })

    # Fast-path : outil déjà exécuté par le routeur d'intention — le LLM ne
    # fait que formuler la réponse à partir du résultat.
    rich = False  # un dossier (recherche, page web) attend une vraie synthèse
    executed: dict[str, str] = {}  # appels déjà faits dans ce tour → jamais deux fois
    if preexecuted is not None:
        name, args, result = preexecuted
        used_tools = True
        rich = name in RICH_TOOLS
        await manager.send(ws, "agent_step", {
            "phase": "tool", "detail": name, "messageId": message_id,
        })
        await manager.send(ws, "tool_result", {"tool": name, "result": str(result)[:300]})
        executed[_call_key(name, args)] = result
        messages = messages + [{
            "role": "user",
            "content": _tool_followup(name, args, result, chain=providers.tier == "cloud"),
        }]

    tag_open = "<JARVIS_TOOL>"
    tool_schemas = tools.schemas() if hasattr(tools, "schemas") else None

    for _iteration in range(MAX_AGENT_ITERATIONS):
        full_response = ""
        sentence_buf = ""
        pending = ""  # tokens retenus tant qu'ils peuvent être un début de balise

        await manager.send(ws, "agent_step", {
            "phase": "thinking",
            "detail": f"Itération {_iteration + 1}",
            "messageId": message_id,
        })

        async def _emit(text: str) -> None:
            nonlocal accumulated, sentence_buf, first_spoken
            if not text:
                return
            await manager.send(ws, "token", {"token": text, "messageId": message_id})
            accumulated += text
            if tts_enabled:
                sentence_buf += text
                m = _SENTENCE_BOUNDARY.search(sentence_buf)
                if m and len(sentence_buf.strip()) > 15:
                    phrase = sentence_buf[: m.start() + 1].strip()
                    sentence_buf = sentence_buf[m.end():]
                    if phrase:
                        first_spoken = True
                        await tts_queue.put(phrase)
                elif not first_spoken and len(sentence_buf) > 70:
                    # Première phrase longue : on la coupe à la virgule pour que
                    # JARVIS commence à parler sans attendre le point.
                    cut = max(sentence_buf.rfind(", "), sentence_buf.rfind("; "), sentence_buf.rfind(" : "))
                    if cut > 25:
                        phrase = sentence_buf[: cut + 1].strip()
                        sentence_buf = sentence_buf[cut + 1:]
                        first_spoken = True
                        await tts_queue.put(phrase)

        in_tool_tag = False
        async for token in providers.stream(
            system, messages,
            max_tokens=max(max_tokens, _RICH_MAX_TOKENS) if rich else max_tokens,
            on_fallback=_notify_fallback,
            # Après un outil, la reformulation est triviale : cerveau le plus rapide.
            # Sauf pour un dossier à synthétiser : là il faut un vrai cerveau.
            level=("deep" if level == "deep" else "standard") if rich
            else "instant" if (preexecuted is not None or used_tools) and level != "deep" else level,
            on_route=_notify_route,
            # Appel de fonction natif pour les cerveaux cloud qui le gèrent.
            tools=tool_schemas,
        ):
            full_response += token
            if in_tool_tag:
                # Cloud : on laisse finir le flux, d'autres appels (parallèles)
                # peuvent suivre. Local : le 7B divague après la balise → stop.
                if providers.tier == "local" and "</JARVIS_TOOL>" in full_response:
                    break
                continue

            pending += token
            idx = pending.find(tag_open)
            if idx != -1:
                # Balise détectée : émettre le texte avant, retenir le reste
                await _emit(pending[:idx])
                pending = ""
                in_tool_tag = True
                if providers.tier == "local" and "</JARVIS_TOOL>" in full_response:
                    break
                continue

            # Retenir le plus long suffixe de pending qui est un préfixe de la
            # balise (ex. "<JARVIS_TO") — le reste peut partir au client
            hold = 0
            max_hold = min(len(pending), len(tag_open) - 1)
            for size in range(max_hold, 0, -1):
                if tag_open.startswith(pending[-size:]):
                    hold = size
                    break
            if len(pending) > hold:
                await _emit(pending[: len(pending) - hold])
                pending = pending[len(pending) - hold:] if hold else ""

        # Fin de stream sans balise → flush du buffer retenu
        if not in_tool_tag and pending:
            await _emit(pending)
            pending = ""

        # Appels d'outils présents dans la réponse (plusieurs = exécutés en parallèle)
        calls = parse_tool_calls(full_response)
        if calls:
            logger.info(f"Agent loop iteration {_iteration + 1}: {len(calls)} appel(s) {[c[0] for c in calls]}")

            async def _run_call(name: str, args: dict) -> tuple[str, bool]:
                """Exécute un appel (ou reprend son résultat s'il a déjà été fait)."""
                key = _call_key(name, args)
                if key in executed:
                    # Le cerveau redemande le même appel : on ne ré-exécute pas (un
                    # rappel créé deux fois, un mail envoyé deux fois…), on force la réponse.
                    logger.info(f"Appel répété ignoré : {name}({args})")
                    return executed[key], True
                # Réservé AVANT tout await : un doublon dans le même lot n'est pas relancé.
                executed[key] = "(en cours)"
                await manager.send(ws, "agent_step", {
                    "phase": "tool", "detail": name, "messageId": message_id,
                })
                await manager.send(ws, "tool_result", {"tool": name, "result": f"⚙️ Exécution de {name}..."})
                try:
                    # Thread : les outils sont bloquants (réseau, WMI, PowerShell…)
                    result = str(await asyncio.to_thread(tools.execute, name, **args))
                except Exception as e:
                    result = f"Erreur outil {name}: {e}"
                    logger.error(f"Tool execution error: {e}", exc_info=True)
                executed[key] = result
                await manager.send(ws, "tool_result", {"tool": name, "result": result[:300]})
                return result, False

            outcomes = await asyncio.gather(*(_run_call(n, a) for n, a in calls))
            # Un doublon dans le même lot : son résultat est celui de l'original.
            results = [executed[_call_key(n, a)] if r == "(en cours)" else r for (n, a), (r, _) in zip(calls, outcomes)]
            repeated = all(rep for _, rep in outcomes)
            used_tools = True
            rich = rich or any(n in RICH_TOOLS for n, _ in calls)

            # Leçon apprise : un échec d'outil est mémorisé pour ne pas être répété
            for (name, args), result in zip(calls, results):
                if not lesson_recorded and result.lower().startswith("erreur"):
                    lesson_recorded = True
                    try:
                        from core.persistent_memory import get_memory
                        get_memory().record_lesson(
                            context=user_query,
                            lesson=f"L'outil {name}({args}) a échoué : {result[:120]}",
                        )
                    except Exception:
                        logger.warning("Impossible d'enregistrer la leçon", exc_info=True)

            # Extraire le texte visible avant la balise tool (s'il y en a)
            visible = _TOOL_CALL_RE.sub("", full_response).strip()
            if visible and visible not in accumulated:
                await manager.send(ws, "token", {"token": visible, "messageId": message_id})
                accumulated += visible

            # Enchaînement possible sauf en local, sur un appel répété ou au dernier tour.
            chain = providers.tier == "cloud" and not repeated and _iteration < MAX_AGENT_ITERATIONS - 2
            if len(calls) == 1:
                followup = _tool_followup(calls[0][0], None, results[0], chain=chain)
            else:
                followup = _tools_followup(calls, results, chain=chain)
            # Réinjecter dans le contexte pour la prochaine itération LLM
            messages = messages + [
                {"role": "assistant", "content": full_response},
                {"role": "user", "content": followup},
            ]
            continue  # Prochaine itération

        else:
            # Pas de tool → réponse finale
            # Envoyer ce qui n'a pas encore été streamé
            remaining = _TOOL_CALL_RE.sub("", full_response).strip()
            if remaining and remaining not in accumulated:
                await manager.send(ws, "token", {"token": remaining, "messageId": message_id})
                accumulated += remaining

            # Flush le dernier buffer TTS
            if tts_enabled and sentence_buf.strip():
                await tts_queue.put(sentence_buf.strip())

            break  # Réponse finale → sortir de la boucle

    # ── Passe de vérification (cloud + outils utilisés uniquement) ──────────
    if used_tools and providers.tier == "cloud" and accumulated.strip():
        correction = await _verify_pass(ws, providers, system, messages, accumulated, message_id)
        if correction:
            await manager.send(ws, "token", {"token": f"\n{correction}", "messageId": message_id})
            accumulated += f"\n{correction}"
            if tts_enabled:
                await tts_queue.put(correction)

    return accumulated


async def _verify_pass(
    ws: "WebSocket",
    providers: "ProviderManager",
    system: str,
    messages: list[dict],
    response: str,
    message_id: str,
) -> str:
    """Relecture courte de la réponse (discipline verification). Retourne la
    correction à annoncer, ou '' si la réponse est validée."""
    await manager.send(ws, "agent_step", {
        "phase": "verify", "detail": "Relecture de la réponse", "messageId": message_id,
    })
    verify_messages = messages + [
        {"role": "assistant", "content": response},
        {
            "role": "user",
            "content": (
                "Vérifie ta réponse ci-dessus : répond-elle exactement à la demande "
                "initiale, sans erreur factuelle par rapport aux résultats d'outils ? "
                "Si oui, réponds exactement OK. Sinon, donne uniquement la correction "
                "en une ou deux phrases."
            ),
        },
    ]
    try:
        chunks = [
            token
            async for token in providers.stream(system, verify_messages, max_tokens=200, level="instant")
        ]
    except Exception as e:
        logger.warning(f"Passe de vérification échouée: {e}")
        return ""
    verdict = "".join(chunks).strip()
    if not verdict or verdict.upper().startswith("OK"):
        return ""
    logger.info(f"Vérification: correction émise ({verdict[:80]})")
    return verdict


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("Client WebSocket connecté")

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)
        logger.info("Client WebSocket déconnecté")

    async def send(self, ws: WebSocket, event_type: str, payload: dict) -> None:
        await ws.send_text(json.dumps({"type": event_type, "payload": payload}))


manager = ConnectionManager()


async def _tts_sentence_worker(
    queue: asyncio.Queue[str | None],
    ws: WebSocket,
    tts: TTSManager,
) -> None:
    """Consomme les phrases, synthétise jusqu'à 2 phrases en parallèle et envoie
    les chunks audio dans l'ordre : la phrase suivante est prête quand la
    précédente finit d'être jouée.

    Garantit l'envoi du chunk final même si une synthèse échoue.
    """
    index = 0
    ordered: asyncio.Queue[asyncio.Task | None] = asyncio.Queue()
    slots = asyncio.Semaphore(2)  # Edge coupe les rafales : 2 synthèses simultanées au plus

    async def _synth(sentence: str) -> str | None:
        async with slots:
            return await tts.synthesize(sentence)

    async def _sender() -> None:
        nonlocal index
        while True:
            task = await ordered.get()
            if task is None:
                return
            try:
                audio_b64 = await task
            except Exception as e:
                logger.warning(f"TTS synthesis failed for sentence: {e}")
                continue
            if audio_b64:
                await manager.send(ws, "tts_chunk", {"audio": audio_b64, "final": False, "index": index})
                index += 1

    sender = asyncio.create_task(_sender())
    try:
        while True:
            sentence: str | None = await queue.get()
            if sentence is None:
                break
            await ordered.put(asyncio.create_task(_synth(sentence)))
    finally:
        await ordered.put(None)
        try:
            await sender
        except Exception:
            pass
        try:
            await manager.send(ws, "tts_chunk", {"audio": "", "final": True, "index": index})
        except Exception:
            pass  # WebSocket déjà fermé — normal à la déconnexion


# Tâches d'apprentissage en arrière-plan (référencées pour ne pas être
# ramassées par le GC avant la fin).
_learning_tasks: set[asyncio.Task] = set()


def _previous_assistant(memory: ContextMemory) -> str:
    """Dernière réponse de JARVIS avant le message en cours (contexte des corrections)."""
    return next(
        (m["content"] for m in reversed(memory.get_messages()) if m["role"] == "assistant"), ""
    )


def _learn_in_background(
    ws: WebSocket, providers: ProviderManager, user_text: str, answer: str, previous: str,
) -> None:
    """Mémoire automatique : retient faits durables et leçons après la réponse,
    sans retarder la conversation."""
    async def _run() -> None:
        from core.auto_memory import describe, learn_from_exchange
        learned = await learn_from_exchange(providers, user_text, answer, previous)
        if learned:
            try:
                await manager.send(ws, "memory_update", {
                    "saved": [f.__dict__ for f in learned.saved],
                    "forgotten": learned.forgotten,
                    "lesson": learned.lesson,
                    "summary": describe(learned),
                })
            except Exception:
                pass  # client déconnecté entre-temps : la mémoire est quand même à jour

    task = asyncio.create_task(_run())
    _learning_tasks.add(task)
    task.add_done_callback(_learning_tasks.discard)


def _maintain_conversation(providers: ProviderManager, memory: ContextMemory) -> None:
    """Après chaque réponse : condense ce qui sort de la fenêtre de contexte et
    met à jour l'archive de la session tous les EPISODE_EVERY_TURNS messages."""
    from core.conversation_memory import EPISODE_EVERY_TURNS, save_episode, update_rolling_summary

    async def _run() -> None:
        if memory.evicted:
            await update_rolling_summary(providers, memory)
        if memory.user_turns and memory.user_turns % EPISODE_EVERY_TURNS == 0:
            memory.episode_id = await save_episode(providers, memory.snapshot(), memory.episode_id)

    task = asyncio.create_task(_run())
    _learning_tasks.add(task)
    task.add_done_callback(_learning_tasks.discard)


def _archive_conversation(providers: ProviderManager, memory: ContextMemory) -> None:
    """Archive la session (fin de connexion, historique effacé) en arrière-plan."""
    from core.conversation_memory import save_episode
    snapshot = memory.snapshot()
    task = asyncio.create_task(save_episode(providers, snapshot, snapshot.episode_id))
    _learning_tasks.add(task)
    task.add_done_callback(_learning_tasks.discard)


def _voice_block(uncertain: bool) -> str:
    """Consignes du mode vocal : la réponse sera ENTENDUE, pas lue."""
    block = (
        "\n\n## MODE VOCAL\n\n"
        "Monsieur vous parle au micro et entendra votre réponse. Répondez en une à trois "
        "phrases naturelles, sans liste, titre, lien ni symbole. Le texte vient d'une "
        "transcription automatique : s'il semble incohérent ou incomplet, demandez de répéter "
        "plutôt que d'inventer une intention."
    )
    if uncertain:
        block += (
            " ATTENTION : cette transcription est INCERTAINE. Avant toute action qui modifie "
            "quelque chose (taper du texte, fermer une fenêtre, envoyer un mail, remplir un "
            "formulaire, créer un rappel), reformulez ce que vous avez compris et demandez "
            "confirmation."
        )
    return block


# Cache par connexion du system prompt local (stable → cache KV llama-cpp
# préservé). Clé : id(memory) — une ContextMemory par connexion.
_system_cache: dict[int, str] = {}


async def handle_text_query(
    ws: WebSocket,
    text: str,
    providers: ProviderManager,
    memory: ContextMemory,
    tts: TTSManager,
    tools: ToolRegistry,
    tts_enabled: bool = True,
    voice: bool = False,
    uncertain: bool = False,
) -> None:
    await manager.send(ws, "status", {"status": "processing"})
    previous = _previous_assistant(memory)
    memory.add_user(text)
    message_id = str(uuid.uuid4())

    if providers.tier == "local":
        # Prompt STABLE sur toute la connexion : indispensable au cache KV.
        key = id(memory)
        if key not in _system_cache:
            _system_cache[key] = build_system_prompt("local", text, stable=True)
        system = _system_cache[key]
    else:
        system = build_system_prompt(providers.tier, text)
    from core.conversation_memory import conversation_block
    system += conversation_block(memory)
    if voice:
        system += _voice_block(uncertain)

    # Routeur d'intention : les demandes évidentes exécutent l'outil
    # immédiatement, sans dépendre du LLM pour le déclencher.
    preexecuted: tuple[str, dict, str] | None = None
    from core.intent import fast_route
    route = fast_route(text)
    if route is not None:
        name, args = route
        logger.info(f"Fast-path intent: {name}({args})")
        try:
            result = await asyncio.to_thread(tools.execute, name, **args)
            preexecuted = (name, args, str(result))
        except Exception as e:
            logger.warning(f"Fast-path {name} en échec ({e}) — retour boucle agent")

    from core.providers.router import classify
    level = classify(text, tool_result_ready=preexecuted is not None)
    await manager.send(ws, "agent_step", {
        "phase": "thinking", "detail": f"Niveau {level.upper()}", "messageId": message_id,
    })

    # ── Agent loop (multi-tool, max MAX_AGENT_ITERATIONS) ──────────────────
    tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
    tts_task = None
    if tts_enabled and tts.is_available:
        tts_task = asyncio.create_task(_tts_sentence_worker(tts_queue, ws, tts))

    try:
        final_text = await _agent_loop(
            ws=ws,
            providers=providers,
            tts=tts,
            tools=tools,
            messages=memory.get_messages(),
            tts_enabled=tts_enabled and tts.is_available,
            message_id=message_id,
            tts_queue=tts_queue,
            system=system,
            preexecuted=preexecuted,
            level=level,
        )
    finally:
        if tts_task:
            await tts_queue.put(None)
            await tts_task

    if final_text:
        memory.add_assistant(final_text)
    _learn_in_background(ws, providers, text, final_text, previous)
    _maintain_conversation(providers, memory)

    await manager.send(ws, "agent_step", {"phase": "done", "detail": "", "messageId": message_id})
    await manager.send(ws, "message_done", {"messageId": message_id})
    await manager.send(ws, "status", {"status": "idle"})


async def handle_council_query(
    ws: WebSocket,
    text: str,
    providers: ProviderManager,
    memory: ContextMemory,
    tts: TTSManager,
    tts_enabled: bool = True,
) -> None:
    """Mode Conseil : toutes les IA disponibles répondent en parallèle, la plus
    capable arbitre et synthétise la meilleure réponse."""
    await manager.send(ws, "status", {"status": "processing"})
    previous = _previous_assistant(memory)
    memory.add_user(text)
    message_id = str(uuid.uuid4())

    async def _on_step(phase: str, detail: str) -> None:
        await manager.send(ws, "agent_step", {
            "phase": phase, "detail": detail, "messageId": message_id,
        })

    from core.council import run_council
    best, participants, judge_label = await run_council(text, providers, _on_step)

    if participants:
        await manager.send(ws, "notice", {
            "message": f"Conseil : {', '.join(participants)} — arbitré par {judge_label}",
        })

    await manager.send(ws, "token", {"token": best, "messageId": message_id})
    memory.add_assistant(best)
    _learn_in_background(ws, providers, text, best, previous)
    _maintain_conversation(providers, memory)

    if tts_enabled and tts.is_available and best:
        tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
        tts_task = asyncio.create_task(_tts_sentence_worker(tts_queue, ws, tts))
        try:
            for sentence in tts.split_sentences(best):
                await tts_queue.put(sentence)
        finally:
            await tts_queue.put(None)
            await tts_task

    await manager.send(ws, "agent_step", {"phase": "done", "detail": "", "messageId": message_id})
    await manager.send(ws, "message_done", {"messageId": message_id})
    await manager.send(ws, "status", {"status": "idle"})


async def transcribe(
    audio_buffer: list[list[float]], sample_rate: int, stt: STTManager, providers: ProviderManager,
) -> tuple[str, bool]:
    """Voix → (texte, incertain). Cloud (Groq/OpenAI Whisper large) si une clé
    est configurée, sinon ou en cas d'échec Whisper local."""
    audio = await asyncio.to_thread(STTManager.prepare, audio_buffer, sample_rate)
    if audio is None:
        return "", False
    from core import cloud_stt
    text = await cloud_stt.transcribe(audio, providers)
    if text is not None:
        return text, False
    return await stt.transcribe_audio(audio)


def voice_available(stt: STTManager, providers: ProviderManager) -> bool:
    from core import cloud_stt
    return stt.is_available or bool(cloud_stt.engines(providers))


async def transcribe_and_query(
    ws: WebSocket,
    audio_buffer: list[list[float]],
    sample_rate: int,
    stt: STTManager,
    providers: ProviderManager,
    memory: ContextMemory,
    tts: TTSManager,
    tools: ToolRegistry,
    tts_enabled: bool = True,
) -> None:
    if not audio_buffer:
        return
    text, uncertain = await transcribe(audio_buffer, sample_rate, stt, providers)
    logger.info(f"STT transcription: {text!r}{' (incertaine)' if uncertain else ''}")
    if text.strip():
        await manager.send(ws, "stt_text", {"text": text.strip(), "uncertain": uncertain})
        await handle_text_query(
            ws, text.strip(), providers, memory, tts, tools, tts_enabled,
            voice=True, uncertain=uncertain,
        )
    else:
        await manager.send(ws, "status", {"status": "idle"})


async def websocket_handler(
    ws: WebSocket,
    providers: ProviderManager,
    stt: STTManager,
    tts: TTSManager,
    tools: ToolRegistry,
    max_context_messages: int = 20,
) -> None:
    # Origin check — reject connections from unexpected origins (en mode web,
    # le middleware d'accès a déjà validé l'origine ET la session).
    from api.security import get_access
    origin = ws.headers.get("origin", "")
    if origin and not get_access().web and origin not in ALLOWED_ORIGINS:
        logger.warning(f"Origine WebSocket refusée: {origin!r}")
        await ws.close(code=4403, reason="Origin not allowed")
        return

    await manager.connect(ws)
    ws_id = id(ws)

    from core.monitor import subscribe as _monitor_subscribe, unsubscribe as _monitor_unsubscribe
    alert_queue = _monitor_subscribe()

    async def _forward_alerts():
        while True:
            try:
                alert = await asyncio.wait_for(alert_queue.get(), timeout=1.0)
                await manager.send(ws, alert["type"], alert["payload"])
                if alert["type"] == "reminder" and tts_enabled and tts.is_available:
                    # Rappel annoncé à voix haute, même sans question en cours.
                    kind = alert["payload"].get("kind")
                    message = alert["payload"].get("message", "")
                    # Une routine (briefing, contrôle PC) est déjà rédigée pour être dite.
                    spoken = message if kind == "routine" else (
                        f"{'Minuteur terminé' if kind == 'timer' else 'Rappel'}, Monsieur : {message}"
                    )
                    audio = await tts.synthesize(spoken)
                    if audio:
                        await manager.send(ws, "tts_audio", {"audio": audio})
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    alert_task = asyncio.create_task(_forward_alerts())

    # Notify client of server capabilities immediately on connect
    await manager.send(ws, "server_status", {
        "llm": providers.is_available,
        "stt": voice_available(stt, providers),
        "tts": tts.is_available,
        "provider": providers.active.name,
        "providerLabel": providers.active.label,
        "providerModel": providers.active.model,
    })

    # Per-connection memory — no shared state between clients
    memory = ContextMemory(int(setting("chat.context_messages") or max_context_messages))
    greeted = False

    audio_buffer: list[list[float]] = []
    current_sample_rate: int = 16000
    speech_detected: bool = False   # de la parole a été entendue dans le buffer
    speech_run: float = 0.0         # secondes de parole consécutives (confirmation)
    silence_run: float = 0.0        # secondes de silence consécutives
    buffered_s: float = 0.0         # durée de l'audio en attente
    tts_enabled: bool = True
    wake_detector = None  # lazy — instancié au 1er wake_audio (modèle stateful par connexion)
    query_task: asyncio.Task | None = None  # requête en cours — annulable via stop_generation
    live = None  # session Gemini Live (conversation vocale temps réel), None hors mode LIVE

    live_turn = {"user": "", "assistant": "", "previous": ""}  # transcriptions du tour LIVE

    async def _live_send(event_type: str, data: dict) -> None:
        # La mémoire automatique apprend aussi des conversations LIVE : les
        # transcriptions arrivent par fragments, on les assemble par tour.
        if event_type == "live_transcript":
            role = "user" if data.get("role") == "user" else "assistant"
            live_turn[role] += str(data.get("text", ""))
        elif event_type == "live_turn_complete":
            user_text = live_turn["user"].strip()
            answer = live_turn["assistant"].strip()
            if user_text:
                _learn_in_background(ws, providers, user_text, answer, live_turn["previous"])
            live_turn.update(user="", assistant="", previous=answer or live_turn["previous"])
        try:
            await manager.send(ws, event_type, data)
        except Exception:
            pass

    async def _live_tool(name: str, args: dict) -> str:
        return str(await asyncio.to_thread(tools.execute, name, **args))

    async def _start_live(voice: str) -> None:
        nonlocal live
        from core.live import LiveSession
        from core.tts import GEMINI_VOICES
        key = providers.api_key("gemini")
        if not key:
            await manager.send(ws, "live_state", {
                "active": False, "error": "Mode LIVE : ajoutez une clé Gemini dans l'onglet CERVEAU.",
            })
            return
        if live is not None:
            await live.stop()
        live = LiveSession(
            api_key=key, send=_live_send, run_tool=_live_tool,
            system=build_system_prompt("cloud", ""),
            tools=tools.schemas(),
            voice=voice if voice in GEMINI_VOICES else "Charon",
            model=setting("live.model"),
        )
        try:
            await live.start()
        except Exception as e:
            logger.warning(f"Gemini Live indisponible: {e}")
            await live.stop(error=f"Gemini Live indisponible : {str(e)[:160]}")
            live = None

    async def _run_query(coro) -> None:
        """Exécute une requête en tâche de fond ; garantit le retour à idle
        même sur annulation (bouton STOP) ou erreur."""
        try:
            await coro
        except asyncio.CancelledError:
            logger.info("Génération interrompue par Monsieur")
            try:
                await manager.send(ws, "notice", {"message": "Génération interrompue."})
                await manager.send(ws, "status", {"status": "idle"})
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Erreur requête: {e}", exc_info=True)
            try:
                await manager.send(ws, "error", {"message": "Erreur interne du serveur."})
                await manager.send(ws, "status", {"status": "idle"})
            except Exception:
                pass

    try:
        while True:
            raw = await ws.receive_text()

            if len(raw) > MAX_PAYLOAD_BYTES:
                logger.warning(f"Payload trop grand: {len(raw)} bytes")
                continue

            event = json.loads(raw)
            event_type: str = event.get("type", "")
            payload: dict = event.get("payload", {})

            if event_type == "text_query" and live is not None and live.active:
                # Texte tapé pendant une session LIVE : réponse vocale de Gemini.
                text = str(payload.get("text", "")).strip()[:MAX_TEXT_CHARS]
                if text:
                    await live.send_text(text)

            elif event_type == "text_query":
                if not _rate_limiter.allow_text(ws_id):
                    await manager.send(ws, "error", {"message": "Trop de requêtes. Patientez une minute."})
                    continue
                text = str(payload.get("text", "")).strip()
                if not text:
                    continue
                text = text[:MAX_TEXT_CHARS]
                council = bool(payload.get("council", False))
                # Une seule requête à la fois — la nouvelle remplace l'ancienne
                if query_task is not None and not query_task.done():
                    query_task.cancel()
                if council and len(providers.council_members()) >= 2:
                    coro = handle_council_query(ws, text, providers, memory, tts, tts_enabled)
                else:
                    coro = handle_text_query(ws, text, providers, memory, tts, tools, tts_enabled)
                query_task = asyncio.create_task(_run_query(coro))

            elif event_type == "live_start":
                await _start_live(str(payload.get("voice", "Charon")))

            elif event_type == "live_stop":
                if live is not None:
                    await live.stop()
                    live = None

            elif event_type == "audio_chunk" and live is not None and live.active:
                # Mode LIVE : le micro part directement vers Gemini (pas de Whisper).
                if not _rate_limiter.allow_audio(ws_id):
                    continue
                chunk_data = payload.get("data")
                if isinstance(chunk_data, list) and chunk_data:
                    await live.send_audio(chunk_data, int(payload.get("sampleRate", 16000)))

            elif event_type == "stop_generation":
                if query_task is not None and not query_task.done():
                    query_task.cancel()
                else:
                    await manager.send(ws, "status", {"status": "idle"})

            elif event_type == "audio_chunk":
                if not _rate_limiter.allow_audio(ws_id):
                    continue
                if voice_available(stt, providers):
                    chunk_data = payload.get("data")
                    if not isinstance(chunk_data, list):
                        continue
                    current_sample_rate = int(payload.get("sampleRate", 16000)) or 16000
                    chunk_s = len(chunk_data) / current_sample_rate
                    audio_buffer.append(chunk_data)
                    buffered_s += chunk_s
                    if len(audio_buffer) == 1:
                        await manager.send(ws, "status", {"status": "listening"})

                    # Détection de fin de parole : RMS du chunk
                    _sq = 0.0
                    for _v in chunk_data:
                        _sq += _v * _v
                    _rms = (_sq / max(len(chunk_data), 1)) ** 0.5
                    if _rms >= setting("voice.speech_threshold"):
                        speech_run += chunk_s
                        silence_run = 0.0
                        if speech_run >= SPEECH_CONFIRM_S:
                            speech_detected = True
                    else:
                        speech_run = 0.0
                        silence_run += chunk_s

                    if not speech_detected:
                        # Pas encore de parole : ne garder qu'un court pré-roll —
                        # jamais des secondes de silence envoyées à Whisper.
                        while len(audio_buffer) > 1 and buffered_s - len(audio_buffer[0]) / current_sample_rate >= PRE_ROLL_S:
                            buffered_s -= len(audio_buffer.pop(0)) / current_sample_rate
                        continue

                    end_of_speech = silence_run * 1000 >= setting("voice.end_silence_ms")
                    overflow = buffered_s >= setting("voice.max_utterance_s")
                    if end_of_speech or overflow:
                        chunks = list(audio_buffer)
                        audio_buffer.clear()
                        buffered_s = 0.0
                        speech_detected = False
                        speech_run = 0.0
                        silence_run = 0.0
                        if query_task is not None and not query_task.done():
                            query_task.cancel()
                        query_task = asyncio.create_task(_run_query(transcribe_and_query(
                            ws, chunks, current_sample_rate, stt, providers, memory, tts, tools, tts_enabled
                        )))

            elif event_type == "wake_audio":
                # Mode veille : frames analysées pour « Hey Jarvis » uniquement,
                # jamais bufferisées pour le STT. PAS de rate limiter ici : la
                # veille émet ~12 chunks/s en continu — la limite de 300/min
                # s'épuisait en 25 s et tuait silencieusement la détection.
                chunk_data = payload.get("data")
                if not isinstance(chunk_data, list) or len(chunk_data) > 20000:
                    continue
                if wake_detector is None:
                    from core.wakeword import WakeWordDetector
                    wake_detector = WakeWordDetector()
                    logger.info("Mode veille « Hey Jarvis » actif sur cette connexion")
                    if not wake_detector.is_available:
                        await manager.send(ws, "wake_unavailable", {})
                        continue
                sr = int(payload.get("sampleRate", 16000))
                if await wake_detector.feed(chunk_data, sr):
                    await manager.send(ws, "wake", {})

            elif event_type == "wake_reset":
                if wake_detector is not None:
                    wake_detector.reset()

            elif event_type == "mic_stop":
                if not speech_detected:
                    # Que du silence dans le buffer — rien à transcrire
                    audio_buffer.clear()
                    buffered_s = 0.0
                    speech_run = 0.0
                    silence_run = 0.0
                    await manager.send(ws, "status", {"status": "idle"})
                    continue
                speech_detected = False
                speech_run = 0.0
                silence_run = 0.0
                if audio_buffer and voice_available(stt, providers):
                    chunks = list(audio_buffer)
                    audio_buffer.clear()
                    buffered_s = 0.0
                    if query_task is not None and not query_task.done():
                        query_task.cancel()
                    query_task = asyncio.create_task(_run_query(transcribe_and_query(
                        ws, chunks, current_sample_rate, stt, providers, memory, tts, tools, tts_enabled
                    )))
                else:
                    audio_buffer.clear()
                    await manager.send(ws, "status", {"status": "idle"})

            elif event_type == "tts_done":
                await manager.send(ws, "status", {"status": "idle"})

            elif event_type == "set_tts":
                tts_enabled = bool(payload.get("enabled", True))
                logger.info(f"TTS {'activé' if tts_enabled else 'désactivé'}")

            elif event_type == "set_voice":
                voice_id = str(payload.get("voice", "")).strip()
                if voice_id.startswith("gemini:"):
                    from core.tts import GEMINI_VOICES
                    name = voice_id[7:]
                    if name in GEMINI_VOICES:
                        tts.set_gemini_voice(name)
                    else:
                        logger.warning(f"Voix Gemini inconnue: {name}")
                elif voice_id.startswith("edge:"):
                    # Voix neurale Edge-TTS — validation stricte du nom
                    edge_name = voice_id[5:]
                    if re.fullmatch(r"[a-zA-Z]{2}-[a-zA-Z]{2}-[a-zA-Z0-9]+", edge_name):
                        tts.set_edge_voice(edge_name)
                    else:
                        logger.warning(f"Nom de voix Edge invalide: {edge_name!r}")
                elif voice_id:
                    voice_path = MODELS_DIR / "piper" / f"{voice_id}.onnx"
                    if voice_path.exists():
                        tts.set_voice(voice_path)
                    else:
                        logger.warning(f"Voix introuvable: {voice_path}")

            elif event_type == "greet":
                # Ouverture de l'application : accueil parlé, une fois par connexion.
                if not greeted and setting("assistant.greeting"):
                    greeted = True
                    from core.greeting import build_greeting
                    text = await asyncio.to_thread(
                        build_greeting, None, bool(setting("assistant.greeting_briefing")),
                        str(setting("assistant.user_title")))
                    memory.add_assistant(text)
                    await manager.send(ws, "greeting", {"text": text})
                    if tts_enabled and tts.is_available:
                        audio = await tts.synthesize(text)
                        if audio:
                            await manager.send(ws, "tts_audio", {"audio": audio})

            elif event_type == "preview_voice":
                # Paramètres › Voix : fait entendre la voix choisie.
                if tts.is_available:
                    audio = await tts.synthesize(
                        "Bonjour Monsieur. Voici ma voix : tous les systèmes sont opérationnels."
                    )
                    if audio:
                        await manager.send(ws, "tts_audio", {"audio": audio})
                    else:
                        await manager.send(ws, "error", {"message": "Cette voix n'a rien produit : vérifiez la clé ou la connexion."})

            elif event_type == "clear_history":
                _archive_conversation(providers, memory)
                memory.clear()
                logger.info("Historique effacé")

            else:
                logger.warning(f"Type d'événement inconnu: {event_type}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}", exc_info=True)
        audio_buffer.clear()
        try:
            await manager.send(ws, "error", {"message": "Erreur interne du serveur."})
        except Exception:
            pass
    finally:
        if query_task is not None and not query_task.done():
            query_task.cancel()
        if live is not None:
            await live.stop()
        alert_task.cancel()
        _monitor_unsubscribe(alert_queue)
        _rate_limiter.cleanup(ws_id)
        _system_cache.pop(id(memory), None)
        _archive_conversation(providers, memory)
        manager.disconnect(ws)
