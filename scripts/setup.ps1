#Requires -Version 5.1
<#
.SYNOPSIS
    Setup JARVIS - installe les dépendances Python et npm.
.PARAMETER SkipModels
    Ne pas télécharger les modèles IA (utile si déjà présents).
#>
param(
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "[JARVIS SETUP] Vérification Python 3.12..." -ForegroundColor Cyan
$PythonExe = (Get-Command "py" -ErrorAction SilentlyContinue)
if (-not $PythonExe) {
    Write-Host "[ERREUR] Python Launcher 'py' introuvable. Installez Python 3.12." -ForegroundColor Red
    exit 1
}

Write-Host "[JARVIS SETUP] Création du venv Python 3.12..." -ForegroundColor Cyan
Set-Location "$Root\server"
if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

Write-Host "[JARVIS SETUP] Installation des dépendances Python..." -ForegroundColor Cyan
& ".\.venv\Scripts\pip.exe" install fastapi "uvicorn[standard]" websockets faster-whisper openwakeword psutil pyautogui pydantic pydantic-settings sounddevice numpy scipy python-multipart aiofiles

Write-Host "[JARVIS SETUP] Installation llama-cpp-python (CUDA 12.1)..." -ForegroundColor Cyan
& ".\.venv\Scripts\pip.exe" install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

Write-Host "[JARVIS SETUP] Installation npm (frontend)..." -ForegroundColor Cyan
Set-Location "$Root\client"
npm install

if (-not $SkipModels) {
    $ModelDir = "$Root\server\models"
    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

    $ModelPath = "$ModelDir\mistral-7b-instruct-v0.3.Q4_K_M.gguf"
    if (-not (Test-Path $ModelPath)) {
        Write-Host "[JARVIS SETUP] Téléchargement Mistral-7B Q4 (~4.4 GB)..." -ForegroundColor Yellow
        $ModelUrl = "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/mistral-7b-instruct-v0.3.Q4_K_M.gguf"
        Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelPath -UseBasicParsing
    } else {
        Write-Host "[JARVIS SETUP] Modèle LLM déjà présent." -ForegroundColor Green
    }

    Write-Host "[JARVIS SETUP] RAPPEL: Téléchargez manuellement Piper TTS:" -ForegroundColor Yellow
    Write-Host "  - piper.exe depuis https://github.com/rhasspy/piper/releases" -ForegroundColor Yellow
    Write-Host "  - en_US-lessac-high.onnx + .json" -ForegroundColor Yellow
    Write-Host "  - Placer dans: $Root\server\models\piper\" -ForegroundColor Yellow
}

Write-Host "[JARVIS SETUP] [OK] Setup terminé!" -ForegroundColor Green
Write-Host ""
Write-Host "Pour démarrer JARVIS en mode développement:" -ForegroundColor Cyan
Write-Host "  1. cd server; .\.venv\Scripts\Activate.ps1; python main.py" -ForegroundColor White
Write-Host "  2. cd client; npx tauri dev" -ForegroundColor White
