from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class ProviderError(RuntimeError):
    """Échec d'un provider LLM (réseau, auth, quota) — déclenche le fallback local."""


class LLMProvider(ABC):
    """Contrat commun des cerveaux LLM de JARVIS.

    Le tool-calling passe par les balises <JARVIS_TOOL> dans le texte généré,
    identique pour tous les providers — la boucle agent reste inchangée quel que
    soit le cerveau actif.
    """

    name: str = "base"
    label: str = "Base"
    tier: str = "cloud"  # "local" | "cloud" — sélectionne la variante des skills
    # Appel de fonction natif : les appels d'outils sont convertis en balises
    # <JARVIS_TOOL> dans le flux, la boucle agent reste identique.
    native_tools: bool = False

    @property
    @abstractmethod
    def is_available(self) -> bool: ...

    @property
    @abstractmethod
    def model(self) -> str: ...

    def warm_target(self) -> tuple[str, dict[str, str]] | None:
        """URL légère (liste des modèles) pour ouvrir la connexion à l'avance, ou None."""
        return None

    @abstractmethod
    def stream(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Génère la réponse token par token. Lève ProviderError en cas d'échec.

        `tools` : schémas {name, description, parameters}, ignorés si le
        provider ne gère pas l'appel de fonction natif."""


def tool_tag(name: str, args: dict) -> str:
    """Balise d'appel d'outil comprise par la boucle agent."""
    import json
    return f'<JARVIS_TOOL>{json.dumps({"name": name, "args": args}, ensure_ascii=False)}</JARVIS_TOOL>'


def parse_tool_args(raw: str) -> dict:
    import json
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
