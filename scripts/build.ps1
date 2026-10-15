#Requires -Version 5.1
<#
.SYNOPSIS
    Build JARVIS - compile le serveur Python (PyInstaller) + Tauri release.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$ServerDir = "$Root\server"
$ClientDir = "$Root\client"
$ResDir = "$ClientDir\src-tauri\resources"

Write-Host "[BUILD] === JARVIS Build Pipeline ===" -ForegroundColor Cyan

# Step 1: Kill existing processes
Write-Host "[BUILD] Arret des processus JARVIS..." -ForegroundColor Cyan
Get-Process -Name "jarvis_server" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "JARVIS" -ErrorAction SilentlyContinue | Stop-Process -Force

# Step 2: Clean artifacts
Write-Host "[BUILD] Nettoyage..." -ForegroundColor Cyan
@("$ServerDir\dist", "$ServerDir\build") | ForEach-Object {
    Remove-Item -Path $_ -Recurse -Force -ErrorAction SilentlyContinue
}

# Step 3: Interface React (embarquée aussi dans le serveur pour le panneau web --web)
Write-Host "[BUILD] Interface React..." -ForegroundColor Cyan
Set-Location $ClientDir
npm ci --no-audit --no-fund
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Build de l'interface échoué (code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

# Step 4: Build Python -> exe (jarvis_server.spec : outils, skills, interface web)
Write-Host "[BUILD] PyInstaller - packaging serveur Python..." -ForegroundColor Cyan
Set-Location $ServerDir
& ".\.venv\Scripts\pip.exe" install pyinstaller -q
& ".\.venv\Scripts\pyinstaller.exe" --noconfirm --clean jarvis_server.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] PyInstaller a échoué (code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $ResDir | Out-Null
Copy-Item "$ServerDir\dist\jarvis_server.exe" "$ResDir\jarvis_server.exe" -Force
Write-Host "[BUILD] [OK] jarvis_server.exe -> $ResDir" -ForegroundColor Green

# Step 5: Tauri build (installeur NSIS ; le serveur est une ressource du bundle)
Write-Host "[BUILD] Tauri build release..." -ForegroundColor Cyan
Set-Location $ClientDir
# Mises à jour : signature minisign (clé privée hors dépôt, jamais committée).
if (-not $env:TAURI_SIGNING_PRIVATE_KEY -and -not $env:TAURI_SIGNING_PRIVATE_KEY_PATH) {
    $env:TAURI_SIGNING_PRIVATE_KEY_PATH = 'D:\MDP\jarvis-updater.key'
}
if (-not $env:TAURI_SIGNING_PRIVATE_KEY -and -not (Test-Path $env:TAURI_SIGNING_PRIVATE_KEY_PATH)) {
    Write-Host "[ERREUR] Clé de signature introuvable : $env:TAURI_SIGNING_PRIVATE_KEY_PATH" -ForegroundColor Red
    exit 1
}
npx tauri build

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Tauri build a échoué (code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

Write-Host "[BUILD] [OK] Build termine!" -ForegroundColor Green
Write-Host ("[BUILD] Installeur: " + $ClientDir + "\src-tauri\target\release\bundle") -ForegroundColor Cyan
python "$Root\scripts\make-latest-json.py"
Write-Host "[BUILD] Release : téléverser JARVIS_X.Y.Z_x64-setup.exe, son .sig et latest.json (dossier bundle\nsis) sur la release GitHub vX.Y.Z" -ForegroundColor Cyan
Write-Host "[BUILD] Panneau web (sans fenetre native) : jarvis_server.exe --web" -ForegroundColor Cyan
