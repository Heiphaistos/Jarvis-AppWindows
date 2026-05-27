# J.A.R.V.I.S.

**Just A Rather Very Intelligent System**

Assistant IA local Iron Man-style — Tauri v2 + React + Python FastAPI + LLM GGUF CUDA

## Stack
- **Frontend**: Tauri v2 · React 18 · TypeScript · Tailwind CSS
- **Backend**: Python · FastAPI · WebSocket
- **LLM**: Mistral-7B-Instruct Q4_K_M via llama-cpp-python (CUDA)
- **STT**: Faster-Whisper (small)
- **TTS**: Piper TTS

## Prérequis
- NVIDIA GPU (RTX 3070 recommandé, 8GB VRAM)
- CUDA Driver ≥ 591
- Python 3.10+
- Node.js 18+
- Rust + Cargo

## Démarrage rapide
```powershell
# Setup
.\scripts\setup.ps1

# Dev
cd server && .\.venv\Scripts\Activate.ps1 && python main.py
cd client && npx tauri dev
```

## Build
```powershell
.\scripts\build.ps1
```
