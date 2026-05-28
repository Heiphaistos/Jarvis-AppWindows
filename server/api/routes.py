from __future__ import annotations
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from utils.config import MODELS_DIR
from tools.info_tools import get_system_info

router = APIRouter()

_PIPER_DIR = MODELS_DIR / "piper"


class HealthResponse(BaseModel):
    status: str
    version: str


class VoicesResponse(BaseModel):
    voices: list[str]


class SystemInfoResponse(BaseModel):
    info: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


@router.get("/voices", response_model=VoicesResponse)
async def list_voices() -> VoicesResponse:
    voices: list[str] = []
    if _PIPER_DIR.exists():
        for f in _PIPER_DIR.glob("*.onnx"):
            if "tashkeel" not in f.name:
                voices.append(f.stem)
    return VoicesResponse(voices=sorted(voices))


@router.get("/system_info", response_model=SystemInfoResponse)
async def system_info() -> SystemInfoResponse:
    info = await asyncio.to_thread(get_system_info)
    return SystemInfoResponse(info=info)
