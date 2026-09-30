from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Awaitable, Callable, Iterable

from core.providers.base import LLMProvider, ProviderError
from utils.logger import get_logger

logger = get_logger("router")

# ── Niveaux de réflexion ──────────────────────────────────────────────────────
# instant  : salutations, ordres courts, reformulation d'un résultat d'outil
# standard : conversation normale
# deep     : analyse, code, comparaison, rédaction longue, raisonnement
LEVELS = ("instant", "standard", "deep")

MAX_TOKENS = {"instant": 512, "standard": 1536, "deep": 4096}

# Délai avant de lancer le cerveau suivant en parallèle si le premier n'a encore
# rien dit (« hedging ») : on garde la latence du plus rapide sans payer deux
# requêtes à chaque message.
HEDGE_DELAY_S = {"instant": 0.6, "standard": 1.2, "deep": 2.5}

_DEEP_RE = re.compile(
    r"\b(analyse|analyser|explique|expliquer|pourquoi|compare|comparer|comparaison|démontre|"
    r"raisonne|réfléchis|stratégie|architecture|optimise|optimiser|débogue|debug|bug|"
    r"code|script|programme|fonction|algorithme|rédige|rédiger|écris|écrire|résume|résumer|"
    r"plan|planifie|avantages|inconvénients|en détail|étape par étape|dissertation|"
    r"traduis ce|corrige ce|review|audit)\b",
    re.IGNORECASE,
)
# Production de code ou de texte long : toujours le cerveau le plus capable.
_BUILD_RE = re.compile(
    r"\b(code|script|programme|algorithme|fonction|rédige|rédiger|écris|écrire|dissertation|debug|débogue)\b",
    re.IGNORECASE,
)
_INSTANT_RE = re.compile(
    r"^(salut|bonjour|bonsoir|hello|hey|coucou|merci|ok|d'accord|parfait|super|génial|"
    r"ça va|comment vas-tu|qui es-tu|oui|non|stop|arrête|tais-toi|bonne nuit|à plus)\b",
    re.IGNORECASE,
)
_FORCE_DEEP = re.compile(r"^(réfléchis bien|mode (profond|expert)|analyse approfondie)", re.IGNORECASE)
_FORCE_FAST = re.compile(r"^(vite|rapidement|en bref|réponse courte)\b", re.IGNORECASE)


def classify(text: str, tool_result_ready: bool = False) -> str:
    """Choisit le niveau de réflexion d'une demande (heuristique locale, < 1 ms)."""
    t = (text or "").strip()
    if not t:
        return "instant"
    if _FORCE_DEEP.search(t):
        return "deep"
    if _FORCE_FAST.search(t) or tool_result_ready:
        return "instant"
    if "```" in t or len(t) > 400 or t.count("?") >= 3 or _BUILD_RE.search(t):
        return "deep"
    if _DEEP_RE.search(t):
        return "deep" if len(t) > 60 else "standard"
    if len(t) <= 60 and (_INSTANT_RE.search(t) or len(t.split()) <= 6):
        return "instant"
    return "standard"


# ── Télémétrie : latence mesurée de chaque cerveau ────────────────────────────

@dataclass
class BrainStats:
    ttft: float | None = None        # temps jusqu'au 1er token (s), moyenne mobile
    tps: float | None = None         # tokens/s, moyenne mobile
    ok: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    last_error: str = ""
    last_used: float = 0.0

    def as_dict(self) -> dict:
        return {
            "ttft_ms": round(self.ttft * 1000) if self.ttft is not None else None,
            "tokens_per_s": round(self.tps, 1) if self.tps is not None else None,
            "ok": self.ok,
            "failures": self.failures,
            "cooling_down": self.cooldown_until > time.monotonic(),
            "last_error": self.last_error[:200],
        }


_ALPHA = 0.3
_COOLDOWN_S = 90.0


@dataclass
class Telemetry:
    stats: dict[str, BrainStats] = field(default_factory=dict)

    def get(self, key: str) -> BrainStats:
        return self.stats.setdefault(key, BrainStats())

    def success(self, key: str, ttft: float, tokens: int, duration: float) -> None:
        s = self.get(key)
        s.ttft = ttft if s.ttft is None else (1 - _ALPHA) * s.ttft + _ALPHA * ttft
        gen = max(duration - ttft, 1e-3)
        if tokens > 5:
            tps = tokens / gen
            s.tps = tps if s.tps is None else (1 - _ALPHA) * s.tps + _ALPHA * tps
        s.ok += 1
        s.consecutive_failures = 0
        s.last_used = time.time()

    def failure(self, key: str, error: str) -> None:
        s = self.get(key)
        s.failures += 1
        s.consecutive_failures += 1
        s.last_error = error
        if s.consecutive_failures >= 2:
            s.cooldown_until = time.monotonic() + _COOLDOWN_S

    def available(self, key: str) -> bool:
        return self.get(key).cooldown_until <= time.monotonic()

    def snapshot(self) -> dict[str, dict]:
        return {k: v.as_dict() for k, v in self.stats.items()}


def brain_key(provider: LLMProvider) -> str:
    return f"{provider.name}@{provider.model}"


def order_candidates(level: str, providers: Iterable[LLMProvider], telemetry: Telemetry) -> list[LLMProvider]:
    """Retire les cerveaux en quarantaine ; en « instant », le plus rapide mesuré passe devant."""
    ranked = [p for p in providers if telemetry.available(brain_key(p))]
    if level == "instant":
        # Tri stable : un cerveau jamais mesuré garde sa place (estimé à 1 s).
        ranked.sort(key=lambda p: telemetry.get(brain_key(p)).ttft or 1.0)
    return ranked


# ── Course au premier token ───────────────────────────────────────────────────

WinnerCallback = Callable[[LLMProvider, float], Awaitable[None]]


async def hedged_stream(
    candidates: list[LLMProvider],
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    telemetry: Telemetry,
    hedge_delay: float,
    on_winner: WinnerCallback | None = None,
    max_parallel: int = 2,
) -> AsyncGenerator[str, None]:
    """Stream depuis le premier cerveau qui répond.

    Le 1er candidat démarre seul ; s'il n'a produit aucun token après
    `hedge_delay`, le suivant démarre en parallèle (au plus `max_parallel`
    simultanés). Le premier token désigne le gagnant, les autres sont annulés.
    Un cerveau qui échoue avant son 1er token passe la main au suivant.
    Un échec après le 1er token lève ProviderError (texte déjà envoyé).
    """
    if not candidates:
        raise ProviderError("Aucun cerveau disponible")

    events: asyncio.Queue[tuple[int, str, object]] = asyncio.Queue()
    tasks: dict[int, asyncio.Task] = {}
    started_at: dict[int, float] = {}
    queue = list(enumerate(candidates))
    errors: list[str] = []

    async def _run(idx: int, provider: LLMProvider) -> None:
        try:
            async for token in provider.stream(system, messages, max_tokens=max_tokens):
                await events.put((idx, "tok", token))
            await events.put((idx, "end", None))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # ProviderError ou bug du provider : même traitement
            await events.put((idx, "err", e))

    def _launch() -> bool:
        if not queue:
            return False
        idx, provider = queue.pop(0)
        started_at[idx] = time.monotonic()
        tasks[idx] = asyncio.create_task(_run(idx, provider))
        return True

    _launch()
    winner: int | None = None
    ttft = 0.0
    n_tokens = 0
    try:
        while True:
            active = [i for i, t in tasks.items() if not t.done()]
            can_hedge = winner is None and queue and len(active) < max_parallel
            try:
                idx, kind, payload = await asyncio.wait_for(
                    events.get(), timeout=hedge_delay if can_hedge else None,
                )
            except asyncio.TimeoutError:
                logger.info(f"Aucun token après {hedge_delay:.1f} s — cerveau suivant en parallèle")
                _launch()
                continue

            provider = candidates[idx]
            key = brain_key(provider)

            if winner is None:
                if kind == "tok":
                    winner = idx
                    ttft = time.monotonic() - started_at[idx]
                    for other, task in tasks.items():
                        if other != idx:
                            task.cancel()
                    if on_winner is not None:
                        await on_winner(provider, ttft)
                    n_tokens += 1
                    yield str(payload)
                    continue
                # Échec (ou réponse vide) avant tout token : au suivant.
                error = str(payload) if kind == "err" else "réponse vide"
                errors.append(f"{provider.label} ({provider.model}) : {error}")
                telemetry.failure(key, error)
                logger.warning(f"Cerveau {key} écarté : {error}")
                still_running = [i for i, t in tasks.items() if i != idx and not t.done()]
                if not still_running and not _launch():
                    raise ProviderError("Tous les cerveaux ont échoué : " + " | ".join(errors))
                continue

            if idx != winner:
                continue  # restes d'un perdant annulé
            if kind == "tok":
                n_tokens += 1
                yield str(payload)
            elif kind == "end":
                telemetry.success(key, ttft, n_tokens, time.monotonic() - started_at[idx])
                return
            else:
                telemetry.failure(key, str(payload))
                raise ProviderError(f"{provider.label} a échoué en cours de réponse : {payload}")
    finally:
        for task in tasks.values():
            task.cancel()
        # Laisse les perdants se terminer proprement (connexions HTTP fermées).
        await asyncio.gather(*tasks.values(), return_exceptions=True)
