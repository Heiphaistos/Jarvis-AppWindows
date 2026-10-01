from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator, Awaitable, Callable, TYPE_CHECKING

from core.providers.base import LLMProvider, ProviderError
from core.providers.local_llama import LocalLlamaProvider
from core.providers.anthropic_provider import AnthropicProvider
from core.providers.openai_compat import OpenAICompatProvider
from core.providers.http import warm
from core.providers.router import (
    HEDGE_DELAY_S, LEVELS, MAX_TOKENS, Telemetry, brain_key, hedged_stream, order_candidates,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from core.llm import LLMManager

logger = get_logger("providers")

# Presets d'APIs connues. "custom" accepte n'importe quel endpoint
# OpenAI-compatible — l'app prend donc en charge n'importe quelle API.
PRESETS: dict[str, dict] = {
    "anthropic":  {"kind": "anthropic", "label": "Anthropic (Claude)",
                   "base_url": "https://api.anthropic.com", "model": "claude-opus-5-5", "needs_key": True},
    "openai":     {"kind": "openai", "label": "OpenAI",
                   "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "needs_key": True},
    "gemini":     {"kind": "openai", "label": "Google Gemini",
                   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash", "needs_key": True},
    "ollama":     {"kind": "openai", "label": "Ollama (local)",
                   "base_url": "http://localhost:11434/v1", "model": "llama3.2", "needs_key": False},
    "groq":       {"kind": "openai", "label": "Groq",
                   "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "needs_key": True},
    "deepseek":   {"kind": "openai", "label": "DeepSeek",
                   "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "needs_key": True},
    "xai":        {"kind": "openai", "label": "xAI (Grok)",
                   "base_url": "https://api.x.ai/v1", "model": "grok-3-mini", "needs_key": True},
    "openrouter": {"kind": "openai", "label": "OpenRouter (modèles :free)",
                   "base_url": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.3-70b-instruct:free", "needs_key": True},
    "cerebras":   {"kind": "openai", "label": "Cerebras (gratuit, ultra-rapide)",
                   "base_url": "https://api.cerebras.ai/v1", "model": "llama-3.3-70b", "needs_key": True},
    "huggingface": {"kind": "openai", "label": "Hugging Face (gratuit)",
                    "base_url": "https://router.huggingface.co/v1", "model": "meta-llama/Llama-3.3-70B-Instruct", "needs_key": True},
    "mistral":    {"kind": "openai", "label": "Mistral API",
                   "base_url": "https://api.mistral.ai/v1", "model": "mistral-small-latest", "needs_key": True},
    "lmstudio":   {"kind": "openai", "label": "LM Studio (local)",
                   "base_url": "http://localhost:1234/v1", "model": "", "needs_key": False},
    "pollinations": {"kind": "openai", "label": "Pollinations (gratuit, sans clé)",
                     "base_url": "https://text.pollinations.ai/openai", "model": "openai", "needs_key": False},
    "custom":     {"kind": "openai", "label": "API personnalisée",
                   "base_url": "", "model": "", "needs_key": False},
}

# Ordre de préférence pour juger le conseil multi-IA (du plus capable au moins)
_JUDGE_ORDER = [
    "anthropic", "openai", "gemini", "groq", "cerebras", "deepseek", "xai",
    "mistral", "openrouter", "huggingface", "pollinations", "lmstudio",
    "ollama", "custom",
]

_CONFIG_FIELDS = {"api_key", "model", "base_url"}

# APIs dont l'appel de fonction natif est fiable (les autres gardent les balises texte).
_NATIVE_TOOLS = {"openai", "gemini", "groq", "cerebras", "deepseek", "xai", "mistral", "openrouter"}

# Mode AUTO : pour chaque niveau de réflexion, les cerveaux essayés dans l'ordre
# (« preset » ou « preset@modèle »). Seuls ceux dont la clé est configurée sont
# utilisés ; le cerveau local sert toujours de dernier recours.
AUTO = "auto"
DEFAULT_CHAINS: dict[str, list[str]] = {
    "instant": [
        "cerebras", "groq", "gemini@gemini-2.5-flash-lite", "anthropic@claude-haiku-4-5",
        "openai", "mistral", "deepseek", "openrouter", "ollama",
    ],
    "standard": [
        "gemini@gemini-2.5-flash", "anthropic@claude-sonnet-5-5", "openai", "groq",
        "cerebras", "deepseek", "mistral", "xai", "openrouter", "ollama",
    ],
    "deep": [
        "anthropic", "gemini@gemini-2.5-pro", "openai", "deepseek", "xai",
        "gemini@gemini-2.5-flash", "mistral", "openrouter", "ollama",
    ],
}
_SPEC_RE = __import__("re").compile(r"^[a-z0-9_-]{1,40}(@[A-Za-z0-9._:/-]{1,120})?$")

# APIs ajoutées par l'utilisateur depuis l'onglet Cerveau : identifiant « api-… ».
CUSTOM_PREFIX = "api-"
MAX_CUSTOM = 20
_KINDS = ("openai", "anthropic")


def _slug(label: str) -> str:
    import re
    import unicodedata
    text = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:30] or "perso"


def _mask(key: str) -> str:
    return ("••••" + key[-4:]) if len(key) > 4 else ("••••" if key else "")


class ProviderManager:
    """Sélection et configuration runtime du cerveau LLM.

    Config persistée dans data/providers.json (.gitignoré, clés côté serveur
    uniquement) : {"active": "local", "configs": {"<preset>": {api_key, model, base_url}}}
    """

    def __init__(self, local_manager: "LLMManager", data_dir: Path) -> None:
        self._local = LocalLlamaProvider(local_manager)
        self._config_path = data_dir / "providers.json"
        self._active_name = "local"
        self._configs: dict[str, dict] = {}
        # APIs ajoutées par l'utilisateur : {"api-xxx": {"label": ..., "kind": "openai"|"anthropic"}}
        self._custom: dict[str, dict] = {}
        self._chains: dict[str, list[str]] = {k: list(v) for k, v in DEFAULT_CHAINS.items()}
        self._hedging = True
        self.telemetry = Telemetry()
        self._load_config()

    # ── Persistance ─────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        try:
            if self._config_path.exists():
                data = json.loads(self._config_path.read_text(encoding="utf-8"))
                self._active_name = str(data.get("active", "local"))
                custom = data.get("custom", {})
                if isinstance(custom, dict):
                    self._custom = {
                        name: {"label": str(c.get("label") or name)[:60],
                               "kind": c.get("kind") if c.get("kind") in _KINDS else "openai"}
                        for name, c in custom.items()
                        if isinstance(c, dict) and _SPEC_RE.match(name) and name.startswith(CUSTOM_PREFIX)
                    }
                configs = data.get("configs", {})
                if isinstance(configs, dict):
                    self._configs = {
                        name: {k: str(v) for k, v in cfg.items() if k in _CONFIG_FIELDS}
                        for name, cfg in configs.items()
                        if isinstance(cfg, dict) and self.preset(name) is not None
                    }
                routing = data.get("routing", {})
                if isinstance(routing, dict):
                    chains = routing.get("chains", {})
                    if isinstance(chains, dict):
                        for level in LEVELS:
                            if isinstance(chains.get(level), list):
                                self._chains[level] = [str(x) for x in chains[level] if _SPEC_RE.match(str(x))]
                    self._hedging = bool(routing.get("hedging", True))
        except Exception as e:
            logger.warning(f"providers.json illisible ({e}) — retour au provider local")
            self._active_name, self._configs, self._custom = "local", {}, {}
        if self._active_name not in ("local", AUTO) and self._build(self._active_name) is None:
            logger.warning(f"Provider actif '{self._active_name}' non configuré — retour au local")
            self._active_name = "local"

    def _save_config(self) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            json.dumps({
                "active": self._active_name,
                "configs": self._configs,
                "custom": self._custom,
                "routing": {"chains": self._chains, "hedging": self._hedging},
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Construction ────────────────────────────────────────────────────────

    def preset(self, name: str) -> dict | None:
        """Preset intégré ou API ajoutée par l'utilisateur."""
        if name in PRESETS:
            return PRESETS[name]
        custom = self._custom.get(name)
        if custom is None:
            return None
        return {"kind": custom["kind"], "label": custom["label"], "base_url": "", "model": "", "needs_key": False}

    def names(self) -> list[str]:
        """Tous les fournisseurs configurables : presets puis APIs ajoutées."""
        return [*PRESETS, *self._custom]

    def _build(self, name: str, model_override: str | None = None) -> LLMProvider | None:
        if name == "local":
            return self._local
        preset = self.preset(name)
        if preset is None:
            return None
        cfg = self._configs.get(name, {})
        api_key = str(cfg.get("api_key", ""))
        model = str(model_override or cfg.get("model") or preset["model"])
        base_url = str(cfg.get("base_url") or preset["base_url"])
        if not base_url or not model or (preset["needs_key"] and not api_key):
            return None
        if preset["kind"] == "anthropic":
            return AnthropicProvider(api_key=api_key, model=model, base_url=base_url)
        return OpenAICompatProvider(
            name=name, label=preset["label"], base_url=base_url, api_key=api_key, model=model,
            native_tools=name in _NATIVE_TOOLS,
        )

    # ── API publique ────────────────────────────────────────────────────────

    def warm_candidates(self) -> list[LLMProvider]:
        """Cerveaux à garder « chauds » : têtes de chaîne en AUTO, sinon le provider actif."""
        if self.is_auto:
            picked: list[LLMProvider] = []
            for level in LEVELS:
                picked += order_candidates(level, self.candidates(level), self.telemetry)[:2]
        else:
            picked = [self.active]
        seen: set[str] = set()
        out = []
        for p in picked:
            target = p.warm_target()
            if target and target[0] not in seen:
                seen.add(target[0])
                out.append(p)
        return out

    async def warmup(self) -> dict[str, float | None]:
        """Ouvre les connexions TLS à l'avance : le 1er message ne paie pas la poignée de main."""
        providers = self.warm_candidates()
        results = await asyncio.gather(*(warm(*p.warm_target()) for p in providers))
        return {brain_key(p): r for p, r in zip(providers, results)}

    def schedule_warmup(self) -> None:
        try:
            asyncio.get_running_loop().create_task(self.warmup())
        except RuntimeError:
            pass  # hors boucle (tests, démarrage) : la tâche périodique s'en chargera

    def api_key(self, name: str) -> str:
        """Clé API d'un provider (usage serveur uniquement, jamais renvoyée au client)."""
        return str(self._configs.get(name, {}).get("api_key", ""))

    def resolve(self, spec: str) -> LLMProvider | None:
        """« gemini » ou « gemini@gemini-2.5-pro » → provider prêt, ou None si non configuré."""
        name, _, model = spec.partition("@")
        provider = self._build(name, model or None)
        return provider if provider is not None and provider.is_available else None

    def candidates(self, level: str) -> list[LLMProvider]:
        """Cerveaux configurés pour un niveau (sans doublon), dans l'ordre de la chaîne."""
        seen: set[str] = set()
        out: list[LLMProvider] = []
        for spec in self._chains.get(level, []):
            provider = self.resolve(spec)
            if provider is None or provider.name == "local":
                continue
            # Les API sans clé (Ollama, LM Studio…) ne comptent que si l'utilisateur les a réglées.
            preset = self.preset(provider.name)
            if preset is not None and not preset["needs_key"] and provider.name not in self._configs:
                continue
            key = brain_key(provider)
            if key not in seen:
                seen.add(key)
                out.append(provider)
        return out

    @property
    def is_auto(self) -> bool:
        return self._active_name == AUTO

    @property
    def active(self) -> LLMProvider:
        if self.is_auto:
            for level in ("standard", "deep", "instant"):
                chain = self.candidates(level)
                if chain:
                    return chain[0]
            return self._local
        provider = self._build(self._active_name)
        return provider if provider is not None else self._local

    @property
    def tier(self) -> str:
        return self.active.tier

    @property
    def is_available(self) -> bool:
        return self.active.is_available

    def configure(self, name: str, fields: dict) -> str:
        """Met à jour la config d'un provider. Retourne un message d'erreur ou ''."""
        if name == "local" or self.preset(name) is None:
            return f"Provider inconnu ou non configurable: {name}"
        current = dict(self._configs.get(name, {}))
        for key in _CONFIG_FIELDS:
            if key in fields and fields[key] is not None:
                value = str(fields[key]).strip()
                if key == "base_url" and value and not value.startswith(("http://", "https://")):
                    return "base_url doit commencer par http:// ou https://"
                current[key] = value
        self._configs[name] = current
        self._save_config()
        return ""

    def add_custom(self, label: str, base_url: str, model: str = "", api_key: str = "",
                   kind: str = "openai") -> tuple[str, str]:
        """Ajoute une API (compatible OpenAI ou Anthropic). Retourne (identifiant, erreur)."""
        label = " ".join(str(label).split())[:60]
        if not label:
            return "", "Donnez un nom à cette API"
        if kind not in _KINDS:
            return "", f"Type d'API inconnu : {kind}"
        if len(self._custom) >= MAX_CUSTOM:
            return "", f"{MAX_CUSTOM} APIs personnalisées au maximum"
        base_url = str(base_url).strip()
        if not base_url.startswith(("http://", "https://")):
            return "", "L'adresse doit commencer par http:// ou https://"
        base = CUSTOM_PREFIX + _slug(label)
        name, i = base, 2
        while name in PRESETS or name in self._custom:
            name, i = f"{base}-{i}", i + 1
        self._custom[name] = {"label": label, "kind": kind}
        error = self.configure(name, {"base_url": base_url, "model": model, "api_key": api_key})
        if error:
            del self._custom[name]
            return "", error
        return name, ""

    def remove_custom(self, name: str) -> str:
        """Supprime une API ajoutée par l'utilisateur (et la retire des chaînes AUTO)."""
        if name not in self._custom:
            return f"API personnalisée inconnue : {name}"
        del self._custom[name]
        self._configs.pop(name, None)
        for level, chain in self._chains.items():
            self._chains[level] = [x for x in chain if x.partition("@")[0] != name]
        if self._active_name == name:
            self._active_name = "local"
        self._save_config()
        return ""

    def set_routing(self, chains: dict | None = None, hedging: bool | None = None) -> str:
        """Met à jour les chaînes du mode AUTO. Retourne un message d'erreur ou ''."""
        if chains is not None:
            for level, specs in chains.items():
                if level not in LEVELS or not isinstance(specs, list):
                    return f"Niveau inconnu : {level}"
                bad = [x for x in specs if not isinstance(x, str) or not _SPEC_RE.match(x)
                       or x.partition("@")[0] not in (*self.names(), "local")]
                if bad:
                    return f"Cerveau invalide : {bad[0]}"
                self._chains[level] = list(specs)[:12]
        if hedging is not None:
            self._hedging = bool(hedging)
        self._save_config()
        return ""

    def set_active(self, name: str) -> str:
        """Active un provider. Retourne un message d'erreur ou ''."""
        if name == AUTO:
            if not any(self.candidates(level) for level in LEVELS) and not self._local.is_available:
                return "Mode AUTO : configurez au moins une clé API (Gemini, Groq, Anthropic…)."
            self._active_name = AUTO
            self._save_config()
            self.schedule_warmup()
            logger.info("Cerveau actif : AUTO (routage multi-modèles)")
            return ""
        if name != "local" and self.preset(name) is None:
            return f"Provider inconnu: {name}"
        provider = self._build(name)
        if provider is None:
            return f"Provider '{name}' incomplet — clé API, modèle ou base_url manquant."
        self._active_name = name
        self._save_config()
        self.schedule_warmup()
        logger.info(f"Provider actif: {name} ({provider.model})")
        return ""

    def council_members(self) -> list[LLMProvider]:
        """Tous les cerveaux interrogeables : local + chaque provider configuré."""
        members: list[LLMProvider] = []
        if self._local.is_available:
            members.append(self._local)
        for name in self.names():
            provider = self._build(name)
            if provider is not None and provider.is_available:
                members.append(provider)
        return members

    def judge_provider(self) -> LLMProvider:
        """Le cerveau le plus capable disponible — arbitre du conseil."""
        for name in (*_JUDGE_ORDER, *self._custom):
            provider = self._build(name)
            if provider is not None and provider.is_available:
                return provider
        return self._local

    def status(self) -> dict:
        """État complet pour l'UI — les clés API sont masquées."""
        providers = []
        for name in self.names():
            preset = self.preset(name)
            cfg = self._configs.get(name, {})
            providers.append({
                "name": name,
                "custom": name in self._custom,
                "label": preset["label"],
                "kind": preset["kind"],
                "needs_key": preset["needs_key"],
                "base_url": cfg.get("base_url") or preset["base_url"],
                "model": cfg.get("model") or preset["model"],
                "api_key_masked": _mask(str(cfg.get("api_key", ""))),
                "configured": self._build(name) is not None,
            })
        active = self.active
        return {
            "routing": {
                "chains": self._chains,
                "hedging": self._hedging,
                "resolved": {
                    level: [f"{p.label} · {p.model}" for p in self.candidates(level)] for level in LEVELS
                },
                "telemetry": self.telemetry.snapshot(),
            },
            "active": self._active_name,
            "active_label": "AUTO — routage multi-modèles" if self.is_auto else active.label,
            "active_model": active.model,
            "tier": active.tier,
            "local_available": self._local.is_available,
            "providers": providers,
        }

    async def stream(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        on_fallback: Callable[[str], Awaitable[None]] | None = None,
        level: str | None = None,
        on_route: Callable[[LLMProvider, float, str], Awaitable[None]] | None = None,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream depuis le cerveau actif.

        Mode AUTO : chaîne du niveau demandé, course au premier token (hedging),
        repli sur le niveau voisin puis sur le cerveau local. Mode manuel :
        provider actif, repli local si échec avant le 1er token.
        """
        if self.is_auto:
            lvl = level if level in LEVELS else "standard"
            chain = order_candidates(lvl, self.candidates(lvl), self.telemetry)
            # Niveau vide ou en quarantaine : on emprunte les autres niveaux.
            for other in LEVELS:
                if other != lvl:
                    for p in order_candidates(other, self.candidates(other), self.telemetry):
                        if brain_key(p) not in {brain_key(c) for c in chain}:
                            chain.append(p)
            if self._local.is_available:
                chain.append(self._local)

            async def _winner(provider: LLMProvider, ttft: float) -> None:
                if on_route is not None:
                    await on_route(provider, ttft, lvl)

            started = False
            try:
                async for token in hedged_stream(
                    chain, system, messages,
                    max_tokens=max(max_tokens, MAX_TOKENS[lvl]),
                    telemetry=self.telemetry,
                    hedge_delay=HEDGE_DELAY_S[lvl] if self._hedging else 3600.0,
                    on_winner=_winner,
                    tools=tools,
                ):
                    started = True
                    yield token
            except ProviderError as e:
                logger.error(f"Routage AUTO en échec: {e}")
                yield ("\n[Liaison interrompue en cours de réponse, Monsieur.]" if started
                       else "Tous mes cerveaux sont injoignables, Monsieur. Vérifiez les clés API et la connexion.")
            return

        provider = self.active
        started = False
        try:
            async for token in provider.stream(system, messages, max_tokens=max_tokens, tools=tools):
                if not started and on_route is not None:
                    await on_route(provider, 0.0, level or "standard")
                started = True
                yield token
            return
        except ProviderError as e:
            logger.error(f"Provider {provider.name} en échec: {e}")
            if started or provider.name == "local" or not self._local.is_available:
                yield f"\n[{provider.label} a échoué en cours de réponse. Vérifiez la configuration.]"
                return
            if on_fallback is not None:
                await on_fallback(provider.label)
        async for token in self._local.stream(system, messages, max_tokens=max_tokens):
            yield token


_instance: ProviderManager | None = None


def init_provider_manager(local_manager: "LLMManager", data_dir: Path) -> ProviderManager:
    global _instance
    _instance = ProviderManager(local_manager, data_dir)
    return _instance


def get_provider_manager() -> ProviderManager:
    if _instance is None:
        raise RuntimeError("ProviderManager non initialisé — appeler init_provider_manager()")
    return _instance
