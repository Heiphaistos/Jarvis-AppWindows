from __future__ import annotations
import asyncio
from typing import AsyncGenerator, TYPE_CHECKING
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.config import Settings

logger = get_logger("llm")

SYSTEM_PROMPT = (
    "Tu es J.A.R.V.I.S., un assistant IA ultra-intelligent et légèrement sarcastique, "
    "similaire à celui d'Iron Man. Tu réponds en français avec précision et concision. "
    "Tu peux exécuter des commandes système si demandé. "
    "Tu t'adresses à l'utilisateur comme 'Monsieur' par défaut."
)


class LLMManager:
    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._llm: object | None = None

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
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        if self._llm is None:
            yield "Je suis désolé Monsieur, le modèle LLM n'est pas chargé. Veuillez placer un fichier GGUF dans server/models/."
            return

        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        def _generate() -> object:
            return self._llm.create_chat_completion(  # type: ignore[union-attr]
                messages=full_messages,
                max_tokens=1024,
                temperature=0.7,
                stream=True,
            )

        gen = await asyncio.to_thread(_generate)
        for chunk in gen:  # type: ignore[union-attr]
            delta = chunk["choices"][0]["delta"]
            if content := delta.get("content"):
                yield content
