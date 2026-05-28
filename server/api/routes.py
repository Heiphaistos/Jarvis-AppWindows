from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()

MODELS_DIR = Path(__file__).parents[1] / "models" / "piper"


class HealthResponse(BaseModel):
    status: str
    version: str


class VoicesResponse(BaseModel):
    voices: list[str]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


@router.get("/voices", response_model=VoicesResponse)
async def list_voices() -> VoicesResponse:
    voices = []
    if MODELS_DIR.exists():
        for f in MODELS_DIR.glob("*.onnx"):
            # Exclude non-voice files
            if "tashkeel" not in f.name:
                voices.append(f.stem)
    return VoicesResponse(voices=sorted(voices))
