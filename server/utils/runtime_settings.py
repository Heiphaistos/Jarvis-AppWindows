"""Réglages modifiables depuis l'interface (onglets Paramètres).

Persistés dans data/settings.json. Les variables d'environnement historiques
(JARVIS_CLOUD_STT, JARVIS_LIVE_MODEL…) restent prises en compte comme valeurs
par défaut : un déploiement Docker/VPS continue de fonctionner tel quel, mais
tout se règle désormais aussi depuis l'application.
"""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger("settings")

_FALSE = ("0", "false", "off", "non", "no")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _FALSE


@dataclass(frozen=True)
class Spec:
    kind: str                 # "bool" | "int" | "float" | "str" | "choice"
    default_value: Any        # valeur, ou fonction relue à chaque accès (variables d'environnement)
    label: str
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()
    max_len: int = 300
    pattern: str = ""         # expression régulière que doit respecter une valeur non vide
    multiline: bool = False   # texte libre sur plusieurs lignes (consignes)

    @property
    def default(self) -> Any:
        return self.default_value() if callable(self.default_value) else self.default_value


STT_ENGINES = ("auto", "groq", "openai", "local")
_MODEL_RE = r"^[A-Za-z0-9._:/-]+$"

SPECS: dict[str, Spec] = {
    # ── Micro et reconnaissance vocale ──
    "voice.speech_threshold": Spec(
        "float", 0.004, "Seuil de détection de la voix (plus bas = plus sensible)", 0.0005, 0.05),
    "voice.end_silence_ms": Spec(
        "int", 1200, "Silence avant d'envoyer la phrase (ms)", 400, 4000),
    "voice.max_utterance_s": Spec(
        "int", 30, "Durée maximale d'une phrase (s)", 5, 120),
    "voice.stt_engine": Spec(
        "choice", "auto", "Moteur de transcription", choices=STT_ENGINES),
    "voice.cloud_stt": Spec(
        "bool", lambda: _env_bool("JARVIS_CLOUD_STT", True), "Autoriser la transcription dans le cloud"),
    "voice.stt_language": Spec("str", "fr", "Langue parlée (code ISO)", max_len=8, pattern=r"^[a-z]{2,3}$"),
    "voice.groq_stt_model": Spec("str", "whisper-large-v3-turbo", "Modèle de transcription Groq",
                                 max_len=80, pattern=_MODEL_RE),
    "voice.openai_stt_model": Spec("str", "gpt-4o-mini-transcribe", "Modèle de transcription OpenAI",
                                   max_len=80, pattern=_MODEL_RE),
    # ── Synthèse vocale et mode LIVE ──
    "tts.gemini_model": Spec(
        "str", lambda: os.environ.get("JARVIS_GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        "Modèle Gemini de synthèse vocale", max_len=120, pattern=_MODEL_RE),
    "live.model": Spec(
        "str", lambda: os.environ.get("JARVIS_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-09-2025"),
        "Modèle Gemini du mode LIVE", max_len=120, pattern=_MODEL_RE),
    "tts.gemini_style": Spec(
        "str", lambda: os.environ.get(
            "JARVIS_GEMINI_TTS_STYLE",
            "Lis le texte suivant d'une voix grave, calme et posée, avec l'élégance flegmatique "
            "d'un majordome britannique et une pointe d'ironie bienveillante : "),
        "Consigne de ton pour la voix Gemini", max_len=500),
    # ── Comportement de l'assistant ──
    "assistant.instructions": Spec(
        "str", "", "Consignes personnelles ajoutées à chaque conversation", max_len=2000,
        multiline=True),
    "assistant.greeting": Spec("bool", True, "Accueil vocal à l'ouverture de l'application"),
    "assistant.greeting_briefing": Spec("bool", True, "Annoncer mails non lus et prochain rendez-vous à l'accueil"),
    "assistant.user_title": Spec("str", "Monsieur", "Comment JARVIS vous appelle", max_len=40,
                                 pattern=r"^[\w' .-]{1,40}$"),
    "assistant.response_length": Spec(
        "choice", "normal", "Longueur maximale des réponses", choices=("short", "normal", "long")),
    "chat.context_messages": Spec(
        "int", 30, "Messages gardés en mémoire dans la conversation", 6, 100),
    # ── Mémoire ──
    "memory.auto": Spec("bool", lambda: _env_bool("JARVIS_AUTO_MEMORY", True), "Mémoire automatique"),
    # ── NiTriTe ──
    "nitrite.agent_path": Spec(
        "str", lambda: os.environ.get("JARVIS_NITRITE_AGENT", ""), "Chemin de NiTriTe-Agent.exe", max_len=400,
        # Ce chemin est exécuté : uniquement l'agent NiTriTe, jamais un programme quelconque.
        pattern=r"(?i)^(.*[\\/])?NiTriTe-Agent[^\\/]*\.exe$"),
    "nitrite.session_path": Spec(
        "str", lambda: os.environ.get("JARVIS_NITRITE_SESSION", ""), "Fichier de session de NiTriTe Agent", max_len=400,
        pattern=r"(?i)^.+\.json$"),
}


class SettingsError(ValueError):
    pass


def _coerce(key: str, spec: Spec, value: Any) -> Any:
    try:
        if spec.kind == "bool":
            if isinstance(value, str):
                return value.strip().lower() not in _FALSE
            return bool(value)
        if spec.kind in ("int", "float"):
            num = int(value) if spec.kind == "int" else float(value)
            if spec.minimum is not None and num < spec.minimum:
                raise SettingsError(f"{key} : minimum {spec.minimum}")
            if spec.maximum is not None and num > spec.maximum:
                raise SettingsError(f"{key} : maximum {spec.maximum}")
            return num
        text = str(value).strip().replace("\r\n", "\n")
        if spec.kind == "choice":
            if text not in spec.choices:
                raise SettingsError(f"{key} : valeur attendue parmi {', '.join(spec.choices)}")
            return text
        forbidden = "\r\x00" if spec.multiline else "\r\n\x00"
        if len(text) > spec.max_len or any(c in text for c in forbidden):
            raise SettingsError(f"{key} : valeur invalide")
        if text and spec.pattern and not re.match(spec.pattern, text):
            raise SettingsError(f"{key} : valeur non autorisée")
        return text
    except SettingsError:
        raise
    except (TypeError, ValueError) as e:
        raise SettingsError(f"{key} : {e}") from e


class RuntimeSettings:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._values: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"settings.json illisible ({e}) — valeurs par défaut")
            return
        if not isinstance(raw, dict):
            return
        for key, value in raw.items():
            spec = SPECS.get(key)
            if spec is None:
                continue
            try:
                self._values[key] = _coerce(key, spec, value)
            except SettingsError as e:
                logger.warning(f"Réglage ignoré : {e}")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._values, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def get(self, key: str) -> Any:
        spec = SPECS[key]
        return self._values.get(key, spec.default)

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Valide puis applique toutes les modifications, ou aucune."""
        clean: dict[str, Any] = {}
        for key, value in changes.items():
            spec = SPECS.get(key)
            if spec is None:
                raise SettingsError(f"Réglage inconnu : {key}")
            clean[key] = _coerce(key, spec, value)
        with self._lock:
            for key, value in clean.items():
                if value == SPECS[key].default:
                    self._values.pop(key, None)
                else:
                    self._values[key] = value
            self._save()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {key: self.get(key) for key in SPECS}

    def schema(self) -> dict[str, dict]:
        return {
            key: {
                "kind": s.kind, "label": s.label, "default": s.default,
                "min": s.minimum, "max": s.maximum, "choices": list(s.choices),
            }
            for key, s in SPECS.items()
        }


_instance: RuntimeSettings | None = None


def get_settings() -> RuntimeSettings:
    global _instance
    if _instance is None:
        from utils.paths import data_dir
        _instance = RuntimeSettings(data_dir() / "settings.json")
    return _instance


def setting(key: str) -> Any:
    return get_settings().get(key)
