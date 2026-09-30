import json

from core.llm import parse_tool_call
from core.providers.anthropic_provider import parse_anthropic_sse
from core.providers.openai_compat import parse_openai_sse
from tools.registry import ToolRegistry, tool_schema


async def lines(items):
    for i in items:
        yield i


def sse(obj):
    return "data: " + json.dumps(obj)


async def collect(gen):
    return "".join([x async for x in gen])


async def test_openai_texte_puis_outil():
    stream = [
        sse({"choices": [{"delta": {"content": "Je regarde. "}}]}),
        sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "get_weather", "arguments": '{"ci'}}]}}]}),
        sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'ty": "Paris"}'}}]}}]}),
        sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}),
        "data: [DONE]",
    ]
    out = await collect(parse_openai_sse(lines(stream)))
    assert out.startswith("Je regarde. ")
    assert parse_tool_call(out) == ("get_weather", {"city": "Paris"})


async def test_openai_texte_seul():
    out = await collect(parse_openai_sse(lines([sse({"choices": [{"delta": {"content": "Bonjour"}}]}), "data: [DONE]"])))
    assert out == "Bonjour"


async def test_anthropic_tool_use():
    stream = [
        sse({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
        sse({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Calcul en cours."}}),
        sse({"type": "content_block_stop", "index": 0}),
        sse({"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "t1", "name": "calculate", "input": {}}}),
        sse({"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"expression": '}}),
        sse({"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '"17*23"}'}}),
        sse({"type": "content_block_stop", "index": 1}),
        sse({"type": "message_stop"}),
    ]
    out = await collect(parse_anthropic_sse(lines(stream)))
    assert out.startswith("Calcul en cours.")
    assert parse_tool_call(out) == ("calculate", {"expression": "17*23"})


def test_schemas_depuis_signatures():
    def get_weather(city: str, days: int = 1, detailed: bool = False) -> str:
        """Météo d'une ville.

        Détails ignorés."""
        return ""

    schema = tool_schema(get_weather)
    assert schema["name"] == "get_weather"
    assert schema["description"] == "Météo d'une ville."
    assert schema["parameters"]["required"] == ["city"]
    assert schema["parameters"]["properties"]["days"] == {"type": "integer", "default": 1}
    assert schema["parameters"]["properties"]["detailed"]["type"] == "boolean"


def test_tous_les_outils_ont_un_schema_valide():
    schemas = ToolRegistry().schemas()
    assert len(schemas) >= 28
    for s in schemas:
        assert s["description"] and s["parameters"]["type"] == "object"
        json.dumps(s)
