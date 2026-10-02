@echo off
setlocal
title J.A.R.V.I.S. Web
cd /d "%~dp0"

:: Panneau web : JARVIS sans fenetre native, dans le navigateur deja installe.
:: Plus leger sur les PC modestes (pas de WebView ni de rendu Tauri en plus).
:: L'onglet s'ouvre tout seul, deja connecte (cle dans le lien).
:: Options : --app (fenetre Edge sans onglets), --lan (acces depuis le reseau local)
set "JARVIS_MODELS_DIR=%~dp0models"
start "" "%~dp0jarvis_server.exe" --web %*
endlocal
