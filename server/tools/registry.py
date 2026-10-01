from __future__ import annotations
import importlib
import inspect
import pkgutil
import typing

import tools as _tools_pkg
from utils.logger import get_logger

logger = get_logger("registry")

_SKIP_MODULES = {"registry", "decorator"}


class ToolRegistry:
    """Auto-découvre les fonctions décorées @tool dans les modules de tools/.

    Ajouter un fichier tools/xxx_tools.py avec des fonctions @tool suffit —
    aucune liste manuelle à maintenir.
    """

    def __init__(self) -> None:
        self._tools: dict[str, object] = {}
        self._disabled: dict[str, str] = {}  # nom → raison (outil retiré dans ce mode)
        self._discover()

    def _discover(self) -> None:
        for info in pkgutil.iter_modules(_tools_pkg.__path__):
            if info.name in _SKIP_MODULES or info.name.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"tools.{info.name}")
            except Exception as e:
                logger.error(f"Module tools.{info.name} inchargeable: {e}")
                continue
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                fn = getattr(module, attr_name)
                if callable(fn) and getattr(fn, "_jarvis_tool", False):
                    if fn.__name__ in self._tools and self._tools[fn.__name__] is not fn:
                        logger.warning(f"Outil en doublon ignoré: {fn.__name__} ({info.name})")
                        continue
                    self._tools[fn.__name__] = fn
        logger.info(f"{len(self._tools)} outils découverts")

    def disable(self, names: set[str] | frozenset[str], reason: str) -> int:
        """Retire des outils (absents des schémas, refus explicite s'ils sont
        appelés quand même). Retourne le nombre d'outils retirés."""
        removed = 0
        for name in names:
            if self._tools.pop(name, None) is not None:
                self._disabled[name] = reason
                removed += 1
        if removed:
            logger.info(f"{removed} outils désactivés : {reason}")
        return removed

    def execute(self, name: str, **kwargs) -> str:
        if name in self._disabled:
            return f"Outil {name} indisponible : {self._disabled[name]}"
        if name not in self._tools:
            return f"Outil inconnu: {name}. Disponibles: {', '.join(sorted(self._tools))}"
        try:
            result = self._tools[name](**kwargs)
            return str(result) if result is not None else "Fait."
        except TypeError as e:
            return f"Arguments invalides pour {name}: {e}"
        except Exception as e:
            logger.error(f"Erreur outil {name}: {e}")
            return f"Erreur lors de l'exécution de {name}: {e}"

    def list_tools(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        """Schémas JSON des outils (appel de fonction natif des cerveaux cloud).

        Déduits de la signature (types, valeurs par défaut) et de la docstring :
        aucun schéma à maintenir à la main.
        """
        return [tool_schema(fn) for _, fn in sorted(self._tools.items())]


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


def tool_schema(fn) -> dict:
    """{name, description, parameters} au format JSON Schema pour une fonction @tool."""
    sig = inspect.signature(fn)
    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        hints = {}
    doc = inspect.getdoc(fn) or fn.__name__
    description = doc.split("\n\n")[0].replace("\n", " ").strip()[:500]
    props: dict[str, dict] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        hint = hints.get(name, str)
        origin = typing.get_origin(hint)
        if origin is typing.Union or str(origin) == "<class 'types.UnionType'>":
            args = [a for a in typing.get_args(hint) if a is not type(None)]
            hint = args[0] if args else str
        prop: dict = {"type": _JSON_TYPES.get(typing.get_origin(hint) or hint, "string")}
        if prop["type"] == "array":
            prop["items"] = {"type": "string"}
        if param.default is param.empty:
            required.append(name)
        elif param.default is not None:
            prop["default"] = param.default
        props[name] = prop
    return {
        "name": fn.__name__,
        "description": description,
        "parameters": {"type": "object", "properties": props, "required": required},
    }


# Outils qui agissent sur la machine où tourne le serveur : sur un VPS, ce
# serait le VPS (et non le PC de Monsieur) — retirés de la version hébergée.
HOST_TOOLS = frozenset({
    # fenêtres, clavier
    "list_windows", "window_action", "type_text", "press_keys", "fill_form",
    # fichiers et applications
    "delete_temp_files", "create_file", "move_file", "list_directory", "read_file",
    "open_application", "kill_application", "take_screenshot", "read_clipboard", "write_clipboard",
    # état de la machine
    "get_battery", "set_volume", "get_public_ip", "get_system_info", "diagnose_system",
    "list_processes", "pc_diagnostic", "pc_health_report", "nitrite_start",
    # écran, médias, images du disque
    "media_control", "analyze_screen", "analyze_image",
})
