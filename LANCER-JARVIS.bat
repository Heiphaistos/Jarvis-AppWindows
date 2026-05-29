@echo off
setlocal EnableDelayedExpansion
title J.A.R.V.I.S. v2.0 — Launcher
chcp 65001 >nul 2>&1

echo.
echo  +======================================+
echo  ^|    J.A.R.V.I.S.  v2.0  LAUNCHER    ^|
echo  +======================================+
echo.

:: ── 1. Verifier que le venv Python existe ─────────────────────────────────
if not exist "%~dp0server\.venv\Scripts\python.exe" (
    echo [ERREUR] Python venv manquant.
    echo Executez: python -m venv server\.venv
    echo Puis    : server\.venv\Scripts\pip install -r server\requirements.txt
    pause & exit /b 1
)

:: ── 2. Lancer le serveur IA dans une fenetre visible ─────────────────────
echo [1/3] Demarrage du serveur IA...
echo       ^(Une fenetre "JARVIS Server" va s'ouvrir - chargement LLM 30-60s^)
start "JARVIS Server" /d "%~dp0server" .venv\Scripts\python.exe main.py
echo       Serveur demarre. Attente du chargement des modeles...
echo.

:: ── 3. Attendre que l'API reponde ────────────────────────────────────────
echo [2/3] Attente du serveur ^(max 90s^)...
set /a tries=0
:wait_loop
timeout /t 3 /nobreak >nul
curl -sf http://127.0.0.1:8765/api/health >nul 2>&1
if not errorlevel 1 goto server_ready
set /a tries+=1
set /a elapsed=tries*3
echo       ... !elapsed!s - modeles en cours de chargement...
if !tries! lss 30 goto wait_loop

echo.
echo [ERREUR] Le serveur n'a pas demarre en 90 secondes.
echo Verifiez la fenetre "JARVIS Server" pour voir l'erreur Python.
pause & exit /b 1

:server_ready
echo.
echo [OK] Serveur pret !
echo.

:: ── 4. Lancer l'interface ─────────────────────────────────────────────────
echo [3/3] Lancement de l'interface JARVIS...

if exist "%~dp0client\src-tauri\target\release\JARVIS.exe" (
    echo       Lancement de JARVIS.exe ^(mode production^)...
    start "" "%~dp0client\src-tauri\target\release\JARVIS.exe"
    echo [OK] JARVIS lance !
) else (
    echo       JARVIS.exe non trouve ^(application non compilee^).
    echo       Lancement en MODE DEVELOPPEMENT...
    echo       ^(La compilation Rust prend 2-3 minutes au premier lancement^)
    echo.
    echo       Astuce: lancez build.bat une fois pour creer JARVIS.exe
    echo.
    start "JARVIS App" /d "%~dp0client" cmd /k "npx tauri dev"
    echo [OK] Compilation en cours dans la fenetre "JARVIS App"...
)

echo.
echo  Appuyez sur une touche pour fermer ce launcher.
pause >nul
endlocal
