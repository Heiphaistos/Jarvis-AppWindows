from __future__ import annotations

import base64

import httpx

from utils.logger import get_logger

logger = get_logger("vision")

# Cerveaux capables de voir, par ordre de préférence (clé configurée dans CERVEAU).
_VISION_ORDER = [
    ("gemini", "gemini-2.5-flash"),
    ("anthropic", "claude-opus-5-5"),
    ("openai", "gpt-4o-mini"),
]
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def describe_image(image: bytes, mime: str, question: str) -> str:
    """Pose une question sur une image au premier cerveau visuel configuré (appel synchrone)."""
    from core.providers import get_provider_manager
    from core.providers.manager import PRESETS

    pm = get_provider_manager()
    b64 = base64.b64encode(image).decode()
    prompt = (question or "Décris ce que tu vois, précisément et en français.").strip()[:1000]
    errors: list[str] = []
    for name, model in _VISION_ORDER:
        key = pm.api_key(name)
        if not key:
            continue
        cfg = pm._configs.get(name, {})  # noqa: SLF001 — base_url éventuellement personnalisée
        base = (cfg.get("base_url") or PRESETS[name]["base_url"]).rstrip("/")
        try:
            if name == "anthropic":
                resp = httpx.post(
                    f"{base}/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={
                        "model": model, "max_tokens": 1024,
                        "messages": [{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                            {"type": "text", "text": prompt},
                        ]}],
                    },
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                blocks = resp.json().get("content", [])
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            else:
                resp = httpx.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
                    json={
                        "model": model, "max_tokens": 1024,
                        "messages": [{"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        ]}],
                    },
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"] or ""
            if text.strip():
                return text.strip()
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.warning(f"Vision {name} en échec: {e}")
    if errors:
        return "Analyse visuelle impossible : " + " | ".join(errors)
    return "Aucun cerveau visuel configuré : ajoutez une clé Gemini, Anthropic ou OpenAI dans l'onglet CERVEAU."
