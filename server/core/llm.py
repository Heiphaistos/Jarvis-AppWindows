from __future__ import annotations
import asyncio
import json
import re
from typing import AsyncGenerator, TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("llm")

SYSTEM_PROMPT = (
    "Tu es J.A.R.V.I.S. (Just A Rather Very Intelligent System), l'assistant IA d'Iron Man. "
    "RÈGLES ABSOLUES — NE JAMAIS ENFREINDRE :\n"
    "1. Tu réponds EXCLUSIVEMENT en français, peu importe la langue de la question.\n"
    "2. Tu es élégant, précis, légèrement sarcastique, toujours au service de ton utilisateur.\n"
    "3. Tu t'adresses à l'utilisateur en l'appelant 'Monsieur'.\n"
    "4. Tes réponses sont concises et directes. Pas de bavardage inutile.\n"
    "5. Si on te demande de répondre dans une autre langue, tu refuses poliment en français.\n"
    "6. Pour exécuter une action système, utilise exactement ce format (rien d'autre sur la ligne) :\n"
    "   <JARVIS_TOOL>{\"name\": \"nom_outil\", \"args\": {\"param\": \"valeur\"}}</JARVIS_TOOL>\n"
    "OUTILS DISPONIBLES :\n"
    "  SYSTÈME:\n"
    "    open_application(name) — name ∈ {chrome, firefox, notepad, explorer, calculator, vscode, terminal}\n"
    "    kill_application(name) — ferme un processus autorisé\n"
    "    delete_temp_files() — supprime les fichiers temporaires\n"
    "    get_system_info() — CPU, RAM, GPU, disque\n"
    "    create_file(path, content) — crée un fichier dans le home\n"
    "    move_file(src, dst) — déplace un fichier dans le home\n"
    "  WEB:\n"
    "    web_search(query, max_results=5) — recherche sur internet via DuckDuckGo\n"
    "      → utilise si on demande l'actualité, météo, infos récentes, définitions, prix, etc.\n"
    "  EMAIL:\n"
    "    list_emails(count=5) — affiche les emails non lus de Gmail\n"
    "    send_email(to, subject, body) — envoie un email Gmail\n"
    "Commence directement ta réponse sans préambule."
)

_TOOL_CALL_RE = re.compile(r"<JARVIS_TOOL>(.*?)</JARVIS_TOOL>", re.DOTALL)


def parse_tool_call(response: str) -> tuple[str, dict] | None:
    """Extract tool name and args from a JARVIS_TOOL marker, or None if absent."""
    m = _TOOL_CALL_RE.search(response)
    if not m:
        return None
    try:
        payload = json.loads(m.group(1).strip())
        name = str(payload.get("name", ""))
        args = dict(payload.get("args", {}))
        if name:
            return name, args
    except (json.JSONDecodeError, AttributeError):
        logger.warning(f"Tool call JSON invalide: {m.group(1)!r}")
    return None


class LLMManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._llm: object | None = None
        self._lock = asyncio.Lock()

    def load(self) -> None:
        model_path = self._settings.model_path
        if not model_path.exists():
            logger.warning(f"Modèle LLM introuvable: {model_path}")
            logger.warning("Le LLM sera indisponible. Téléchargez le modèle GGUF.")
            return
        try:
            from llama_cpp import Llama  # type: ignore[import]
            self._llm = Llama(
                model_path=str(model_path),
                n_ctx=self._settings.n_ctx,
                n_gpu_layers=self._settings.n_gpu_layers,
                n_threads=self._settings.n_threads,
                verbose=False,
            )
            logger.info(f"LLM chargé: {model_path.name}")
        except ImportError:
            logger.warning("llama-cpp-python non installé — LLM désactivé")
        except Exception as e:
            logger.error(f"Erreur chargement LLM: {e}")

    def unload(self) -> None:
        self._llm = None
        logger.info("LLM déchargé")

    @property
    def is_available(self) -> bool:
        return self._llm is not None

    async def stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
    ) -> AsyncGenerator[str, None]:
        if self._llm is None:
            yield "Je suis désolé Monsieur, le modèle LLM n'est pas chargé. Veuillez placer un fichier GGUF dans server/models/."
            return

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        def _generate() -> object:
            return self._llm.create_chat_completion(  # type: ignore[union-attr]
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=0.7,
                stream=True,
            )

        async with self._lock:
            gen = await asyncio.to_thread(_generate)
            for chunk in gen:  # type: ignore[union-attr]
                delta = chunk["choices"][0]["delta"]
                if content := delta.get("content"):
                    yield content
