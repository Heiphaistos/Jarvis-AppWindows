@echo off
setlocal EnableDelayedExpansion
title J.A.R.V.I.S. — Launcher
echo.
echo  ╔══════════════════════════════════════╗
echo  ║      J.A.R.V.I.S.  LAUNCHER         ║
echo  ╚══════════════════════════════════════╝

:: Démarrer le serveur Python en arrière-plan
echo [JARVIS] Demarrage du serveur IA...
start "JARVIS-Server" /min /d "%~dp0server" cmd /c ".venv\Scripts\python.exe main.py"

:: Attendre que le serveur soit prêt (max 90s)
echo [JARVIS] Chargement des modeles IA (30-60s)...
where curl >nul 2>&1 || (echo ERREUR: curl.exe introuvable. Windows 10 1803+ requis. & exit /b 1)
set /a tries=0
:wait_loop
timeout /t 3 /nobreak >nul
curl -s http://127.0.0.1:8765/api/health >nul 2>&1
if errorlevel 1 (
    set /a tries+=1
    if !tries! lss 30 goto wait_loop
    echo ERREUR: Le serveur n'a pas demarre en temps voulu.
    exit /b 1
)

echo [JARVIS] Serveur pret ! Lancement de l'interface...

:: Lancer l'app (cherche l'exe compilé, sinon dev mode)
if exist "%~dp0client\src-tauri\target\release\JARVIS.exe" (
    start "" "%~dp0client\src-tauri\target\release\JARVIS.exe"
) else (
    echo [JARVIS] Mode developpement (npm run tauri dev)...
    start "JARVIS-App" /d "%~dp0client" cmd /c "npx tauri dev"
)
endlocal
