from tools.registry import ToolRegistry

EXPECTED_TOOLS = {
    "open_application", "kill_application", "take_screenshot",
    "read_clipboard", "write_clipboard",
    "delete_temp_files", "create_file", "move_file",
    "get_system_info", "diagnose_system", "list_processes", "get_datetime",
    "get_weather", "get_news",
    "web_search",
    "list_emails", "send_email",
    "save_memory", "recall_memory", "list_memories", "forget_memory", "recall_conversations",
    "get_battery", "set_volume", "ping_host",
    "get_public_ip", "list_directory", "read_file",
    "calculate", "convert_units", "translate_text",
    "set_timer", "set_reminder", "list_reminders", "cancel_reminder",
    "read_webpage", "wikipedia_summary", "media_control", "analyze_screen", "analyze_image", "briefing",
}


def test_auto_discovery_41_outils():
    registry = ToolRegistry()
    assert set(registry.list_tools()) == EXPECTED_TOOLS


def test_outil_inconnu():
    registry = ToolRegistry()
    result = registry.execute("outil_fantome")
    assert "Outil inconnu" in result


def test_arguments_invalides():
    registry = ToolRegistry()
    result = registry.execute("calculate", mauvais_argument="2+2")
    assert "Arguments invalides" in result


def test_execution_calculate():
    registry = ToolRegistry()
    assert "4" in registry.execute("calculate", expression="2+2")
