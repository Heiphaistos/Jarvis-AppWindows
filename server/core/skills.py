from __future__ import annotations
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("skills")

_CLOUD_SPLIT = "---cloud---"
_MAX_ROUTED_SKILLS = 4  # au-delà, le prompt local devient contre-productif


def _resolve_skills_dir() -> Path:
    if getattr(sys, "frozen", False):
        beside = Path(sys.executable).parent / "skills"
        if beside.is_dir():
            return beside
        # Sinon, la copie embarquée dans l'exécutable (Linux : l'exe est seul).
        return Path(getattr(sys, "_MEIPASS", beside.parent)) / "skills"
    return Path(__file__).parents[1] / "skills"


@dataclass
class Skill:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    always: bool = False
    body_local: str = ""
    body_cloud: str = ""

    def body(self, tier: str) -> str:
        if tier == "cloud" and self.body_cloud:
            return self.body_cloud
        return self.body_local

    def matches(self, text: str) -> bool:
        if self.always:
            return True
        lowered = text.lower()
        words = set(re.findall(r"[\wàâäéèêëîïôöùûüç'-]+", lowered))
        return any(t in words or (" " in t and t in lowered) for t in self.triggers)


def _parse_skill(path: Path) -> Skill | None:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
    if not m:
        logger.warning(f"Skill sans frontmatter ignoré: {path.name}")
        return None
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    name = meta.get("name", path.stem)
    triggers = [t.strip().lower() for t in meta.get("triggers", "").split(",") if t.strip()]
    always = meta.get("always", "false").lower() == "true"

    body = m.group(2).strip()
    if _CLOUD_SPLIT in body:
        local_part, _, cloud_part = body.partition(_CLOUD_SPLIT)
        body_local, body_cloud = local_part.strip(), cloud_part.strip()
    else:
        body_local = body_cloud = body
    return Skill(
        name=name,
        description=meta.get("description", ""),
        triggers=triggers,
        always=always,
        body_local=body_local,
        body_cloud=body_cloud,
    )


class SkillRouter:
    """Auto-découvre server/skills/*.md et sélectionne les disciplines par intent."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._dir = skills_dir or _resolve_skills_dir()
        self._skills: list[Skill] = []
        self.reload()

    def reload(self) -> None:
        self._skills = []
        if not self._dir.exists():
            logger.warning(f"Répertoire skills introuvable: {self._dir}")
            return
        for path in sorted(self._dir.glob("*.md")):
            try:
                skill = _parse_skill(path)
            except Exception as e:
                logger.warning(f"Skill illisible {path.name}: {e}")
                continue
            if skill is not None:
                self._skills.append(skill)
        logger.info(f"{len(self._skills)} skills chargés: {[s.name for s in self._skills]}")

    @property
    def skills(self) -> list[Skill]:
        return list(self._skills)

    def select(self, user_text: str, tier: str) -> str:
        """Concatène les disciplines actives (always + triggers), plafonné."""
        selected = [s for s in self._skills if s.always]
        routed = [s for s in self._skills if not s.always and s.matches(user_text)]
        selected += routed[:_MAX_ROUTED_SKILLS]
        if not selected:
            return ""
        blocks = [f"### {s.name}\n{s.body(tier)}" for s in selected]
        return "\n\n".join(blocks)


_router: SkillRouter | None = None


def get_router() -> SkillRouter:
    global _router
    if _router is None:
        _router = SkillRouter()
    return _router
