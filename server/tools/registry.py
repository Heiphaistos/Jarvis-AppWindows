from __future__ import annotations
from utils.logger import get_logger

logger = get_logger("registry")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, object] = {}
        self._register_all()

    def _register_all(self) -> None:
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
        from tools.windows_tools import (
            get_battery, set_volume, ping_host,
            get_public_ip, list_directory, read_file,
        )
        from tools.calc_tools import calculate, convert_units, translate_text

        for fn in [
            open_application, kill_application, take_screenshot,
            read_clipboard, write_clipboard,
            delete_temp_files, create_file, move_file,
            get_system_info, diagnose_system, list_processes,
            get_weather, get_news,
            web_search,
            list_emails, send_email,
            save_memory, recall_memory, list_memories,
            get_battery, set_volume, ping_host,
            get_public_ip, list_directory, read_file,
            calculate, convert_units, translate_text,
        ]:
            self._tools[fn.__name__] = fn

    def execute(self, name: str, **kwargs) -> str:
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
