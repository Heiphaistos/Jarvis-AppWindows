from __future__ import annotations
from typing import Callable, Any
from utils.logger import get_logger

logger = get_logger("tools")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        from tools.system_tools import (
            open_application, kill_application,
            take_screenshot, read_clipboard, write_clipboard,
        )
        from tools.file_tools import delete_temp_files, create_file, move_file
        from tools.info_tools import (
            get_system_info, diagnose_system, list_processes,
            get_weather, get_news,
        )
        from tools.web_tools import web_search
        from tools.email_tools import list_emails, send_email
        from tools.memory_tools import save_memory, recall_memory, list_memories

        for fn in [
            open_application, kill_application,
            take_screenshot, read_clipboard, write_clipboard,
            delete_temp_files, create_file, move_file,
            get_system_info, diagnose_system, list_processes,
            get_weather, get_news,
            web_search,
            list_emails, send_email,
            save_memory, recall_memory, list_memories,
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
