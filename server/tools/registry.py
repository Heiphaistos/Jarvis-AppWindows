from __future__ import annotations
from typing import Callable, Any
from utils.logger import get_logger

logger = get_logger("tools")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        from tools.system_tools import open_application, kill_application
        from tools.file_tools import delete_temp_files, create_file, move_file
        from tools.info_tools import get_system_info

        for fn in [
            open_application,
            kill_application,
            delete_temp_files,
            create_file,
            move_file,
            get_system_info,
        ]:
            self._tools[fn.__name__] = fn

    def execute(self, name: str, **kwargs: Any) -> str:
        if name not in self._tools:
            logger.warning(f"Outil non autorisé: {name}")
            return f"Erreur: outil '{name}' non disponible."
        try:
            result = self._tools[name](**kwargs)
            logger.info(f"Outil '{name}' exécuté")
            return str(result)
        except Exception as e:
            logger.error(f"Erreur outil '{name}': {e}")
            return f"Erreur lors de l'exécution de '{name}': {e}"

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
