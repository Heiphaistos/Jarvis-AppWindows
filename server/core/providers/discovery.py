"""Découverte des modèles et test de connexion d'un fournisseur (onglet Cerveau).

Les deux appels utilisent la clé enregistrée côté serveur : elle n'est jamais
renvoyée au client.
"""
from __future__ import annotations

import time

import httpx

from core.providers.http import shared_client
from utils.logger import get_logger

logger = get_logger("providers.discovery")

_TIMEOUT = httpx.Timeout(10.0)
_MAX_MODELS = 400


def _endpoint(pm, name: str) -> tuple[str, str, str, str]:
    """(kind, base_url, api_key, modèle) d'un preset, avec la config enregistrée."""
    preset = pm.preset(name)
    if preset is None:
        raise ValueError(f"Fournisseur inconnu : {name}")
    cfg = pm._configs.get(name, {})  # noqa: SLF001 — lecture interne au package
    base_url = str(cfg.get("base_url") or preset["base_url"]).rstrip("/")
    if not base_url:
        raise ValueError("Adresse de l'API non renseignée")
    api_key = str(cfg.get("api_key", ""))
    if preset["needs_key"] and not api_key:
        raise ValueError("Clé API non enregistrée")
    model = str(cfg.get("model") or preset["model"])
    return preset["kind"], base_url, api_key, model


def _headers(kind: str, api_key: str) -> dict[str, str]:
    if kind == "anthropic":
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _models_url(kind: str, base_url: str) -> str:
    if kind == "anthropic":
        return f"{base_url}/v1/models?limit=1000"
    return f"{base_url}/models"


def _explain(resp: httpx.Response) -> str:
    if resp.status_code in (401, 403):
        return "Clé refusée par le fournisseur (401/403)"
    if resp.status_code == 404:
        return "Adresse introuvable (404) : vérifiez l'URL de l'API"
    if resp.status_code == 429:
        return "Quota ou limite de débit atteint (429)"
    return f"Réponse HTTP {resp.status_code}"


async def list_models(pm, name: str) -> list[str]:
    kind, base_url, api_key, _ = _endpoint(pm, name)
    resp = await shared_client().get(_models_url(kind, base_url), headers=_headers(kind, api_key), timeout=_TIMEOUT)
    if resp.status_code != 200:
        raise ValueError(_explain(resp))
    data = resp.json()
    items = data.get("data", data.get("models", [])) if isinstance(data, dict) else data
    ids: list[str] = []
    for item in items if isinstance(items, list) else []:
        model_id = item.get("id") or item.get("name") if isinstance(item, dict) else item
        if isinstance(model_id, str) and model_id:
            ids.append(model_id.removeprefix("models/"))
    return sorted(set(ids))[:_MAX_MODELS]


async def test_connection(pm, name: str) -> dict:
    """Vérifie l'accès : liste des modèles, et à défaut une mini-requête de chat."""
    kind, base_url, api_key, model = _endpoint(pm, name)
    start = time.perf_counter()
    try:
        models = await list_models(pm, name)
        ms = round((time.perf_counter() - start) * 1000)
        return {"ok": True, "latency_ms": ms, "models": len(models),
                "detail": f"Connexion réussie · {len(models)} modèles disponibles"}
    except (ValueError, httpx.HTTPError) as e:
        list_error = str(e)
    # Certains services n'exposent pas /models : on tente un échange minimal.
    try:
        if kind == "anthropic":
            url = f"{base_url}/v1/messages"
            body = {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
        else:
            url = f"{base_url}/chat/completions"
            body = {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
        resp = await shared_client().post(url, json=body, headers=_headers(kind, api_key), timeout=_TIMEOUT)
    except httpx.HTTPError as e:
        return {"ok": False, "detail": f"Serveur injoignable : {str(e)[:120] or list_error}"}
    ms = round((time.perf_counter() - start) * 1000)
    if resp.status_code == 200:
        return {"ok": True, "latency_ms": ms, "detail": f"Connexion réussie avec le modèle {model}"}
    return {"ok": False, "detail": _explain(resp)}
