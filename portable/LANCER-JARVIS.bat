@echo off
setlocal
title J.A.R.V.I.S. Launcher
cd /d "%~dp0"

echo.
echo   ================================================
echo        J.A.R.V.I.S. v5.5.0 - Portable
echo   ================================================
echo.

:: ── 1. Modele LLM : telechargement auto au premier lancement ──────────────
set "GGUF=models\Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
if not exist "%GGUF%" (
    echo  [1/3] Premier lancement : telechargement du cerveau local
    echo        Mistral-7B-Instruct Q4_K_M — 4,1 GB, une seule fois.
    echo        ^(Ctrl+C pour annuler — JARVIS marchera alors uniquement
    echo         avec un cerveau cloud configure dans les reglages^)
    echo.
    curl.exe -L --retry 5 --retry-delay 3 -C - -o "%GGUF%.part" ^
      "https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
    if errorlevel 1 (
        echo  ATTENTION: telechargement incomplet — relancez ce script pour reprendre.
    ) else (
        move /y "%GGUF%.part" "%GGUF%" >nul
        echo  Modele telecharge.
    )
    echo.
) else (
    echo  [1/3] Modele LLM present.
)

:: ── 1b. Whisper (reconnaissance vocale) : ~465 MB, une seule fois ─────────
set "WDIR=models\faster-whisper-small"
if not exist "%WDIR%\model.bin" (
    echo  [1b/3] Telechargement de la reconnaissance vocale Whisper ^(465 MB^)...
    mkdir "%WDIR%" 2>nul
    for %%F in (model.bin config.json tokenizer.json vocabulary.txt) do (
        if not exist "%WDIR%\%%F" (
            curl.exe -L --retry 5 --retry-delay 3 -C - -o "%WDIR%\%%F" ^
              "https://huggingface.co/Systran/faster-whisper-small/resolve/main/%%F"
        )
    )
    echo.
)

:: ── 2. Serveur ─────────────────────────────────────────────────────────────
echo  [2/3] Demarrage du serveur JARVIS...
set "JARVIS_MODELS_DIR=%~dp0models"
tasklist /FI "IMAGENAME eq jarvis_server.exe" 2>nul | find /i "jarvis_server.exe" >nul
if errorlevel 1 (
    start "JARVIS-Server" /min "%~dp0jarvis_server.exe"
)

:: Attendre le port 8765 (max 120 s — le chargement du modele prend ~30-60 s)
set /a tries=0
:waitloop
curl.exe -s -m 2 http://127.0.0.1:8765/api/health >nul 2>&1 && goto ready
set /a tries+=1
if %tries% geq 60 (
    echo  ATTENTION: le serveur ne repond pas — l'interface s'ouvrira quand meme.
    goto launch
)
timeout /t 2 /nobreak >nul
goto waitloop

:ready
echo         Serveur operationnel.

:launch
:: ── 3. Interface ───────────────────────────────────────────────────────────
echo  [3/3] Ouverture de l'interface...
start "" "%~dp0JARVIS.exe"
echo.
echo  JARVIS est lance. Cette fenetre peut etre fermee.
timeout /t 5 >nul
endlocal
