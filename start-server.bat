@echo off
title JARVIS Core Server
cd /d "%~dp0server"
echo [JARVIS] Demarrage du serveur Python...
echo [JARVIS] Modeles: %~dp0server\models\
.venv\Scripts\python.exe main.py
pause
