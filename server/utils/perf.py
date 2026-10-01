from __future__ import annotations
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("perf")


@dataclass(frozen=True)
class PerfProfile:
    name: str
    label: str
    description: str
    n_gpu_layers: int      # -1 = tout GPU
    n_ctx: int             # fenêtre de contexte llama-cpp
    whisper_compute: str   # float16 (GPU) | int8 (léger)
    max_tokens: int        # longueur max des réponses locales


PROFILES: dict[str, PerfProfile] = {
    "max": PerfProfile(
        name="max", label="Maximal",
        description="Tout le GPU — réponses longues, contexte 8k. ~6,5 GB VRAM.",
        n_gpu_layers=-1, n_ctx=8192, whisper_compute="float16", max_tokens=768,
    ),
    "balanced": PerfProfile(
        name="balanced", label="Équilibré",
        description="GPU complet, contexte 4k, réponses moyennes. ~5,5 GB VRAM.",
        n_gpu_layers=-1, n_ctx=4096, whisper_compute="float16", max_tokens=512,
    ),
    "eco": PerfProfile(
        name="eco", label="Économie",
        description="GPU partiel, contexte 4k, réponses brèves — libère VRAM/CPU pour vos jeux et apps.",
        n_gpu_layers=16, n_ctx=4096, whisper_compute="int8", max_tokens=320,
    ),
}


# Ordre croissant de gourmandise — sert au safe-boot et aux rétrogradations
ORDER = ["eco", "balanced", "max"]

# Plafond de sécurité matériel : la VRAM ne doit jamais rester au-dessus
VRAM_CEILING_PCT = 80.0


def downgrade_of(name: str) -> str | None:
    """Profil un cran en dessous, ou None si déjà au minimum."""
    try:
        idx = ORDER.index(name)
    except ValueError:
        return "eco"
    return ORDER[idx - 1] if idx > 0 else None


def _config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data" / "perf.json"
    return Path(__file__).parents[1] / "data" / "perf.json"


_active: PerfProfile = PROFILES["max"]


def load_profile() -> PerfProfile:
    """Charge le profil persisté (défaut : max)."""
    global _active
    try:
        path = _config_path()
        if path.exists():
            name = json.loads(path.read_text(encoding="utf-8")).get("profile", "max")
            _active = PROFILES.get(name, PROFILES["max"])
    except Exception as e:
        logger.warning(f"perf.json illisible ({e}) — profil max")
        _active = PROFILES["max"]
    logger.info(f"Profil de performance: {_active.label}")
    return _active


def set_profile(name: str) -> PerfProfile | None:
    """Active et persiste un profil. None si inconnu."""
    global _active
    profile = PROFILES.get(name)
    if profile is None:
        return None
    _active = profile
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"profile": name}), encoding="utf-8")
    logger.info(f"Profil de performance changé: {profile.label}")
    return profile


def active_profile() -> PerfProfile:
    return _active


def status() -> dict:
    return {
        "active": _active.name,
        "profiles": [asdict(p) for p in PROFILES.values()],
    }
