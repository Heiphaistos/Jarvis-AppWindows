@echo off
setlocal EnableDelayedExpansion
title JARVIS — Build System
echo.
echo  ╔══════════════════════════════════════╗
echo  ║       J.A.R.V.I.S.  BUILD           ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── 1. Vérifications préalables ──────────────────────────────────────────
echo [1/5] Verification des dependances...
where node >nul 2>&1 || (echo ERREUR: Node.js manquant & exit /b 1)
where cargo >nul 2>&1 || (echo ERREUR: Rust/Cargo manquant & exit /b 1)
if not exist "server\.venv\Scripts\python.exe" (
    echo ERREUR: venv Python manquant - lancez: python -m venv server\.venv
    exit /b 1
)
if not exist "server\models\Mistral-7B-Instruct-v0.3-Q4_K_M.gguf" (
    echo AVERTISSEMENT: Modele LLM manquant dans server\models\
)

:: ── 2. Kill processus existants ───────────────────────────────────────────
echo [2/5] Arret des processus existants...
taskkill /F /IM "JARVIS.exe" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq JARVIS-Server" >nul 2>&1
timeout /t 2 /nobreak >nul

:: ── 3. Build frontend React ───────────────────────────────────────────────
echo [3/5] Build frontend React...
cd client
call npm install --silent
call npm run build
if errorlevel 1 (cd .. & echo ERREUR: Build React echoue & exit /b 1)

:: ── 4. Build Tauri (app + installer NSIS) ────────────────────────────────
echo [4/5] Build Tauri (peut prendre 3-5 minutes)...
call npx tauri build
if errorlevel 1 (cd .. & echo ERREUR: Build Tauri echoue & exit /b 1)

:: ── 5. Résumé ─────────────────────────────────────────────────────────────
echo [5/5] Build termine !
echo.
echo  Executables generes:
echo   - Installer : client\src-tauri\target\release\bundle\nsis\JARVIS_1.0.0_x64-setup.exe
echo   - Portable  : client\src-tauri\target\release\JARVIS.exe
echo.

cd ..
endlocal
