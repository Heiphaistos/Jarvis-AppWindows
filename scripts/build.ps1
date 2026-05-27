#Requires -Version 5.1
<#
.SYNOPSIS
    Build JARVIS - compile le serveur Python (PyInstaller) + Tauri release.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$ServerDir = "$Root\server"
$ClientDir = "$Root\client"
$BinDir = "$ClientDir\src-tauri\binaries"

Write-Host "[BUILD] === JARVIS Build Pipeline ===" -ForegroundColor Cyan

# Step 1: Kill existing processes
Write-Host "[BUILD] Arret des processus JARVIS..." -ForegroundColor Cyan
Get-Process -Name "jarvis-server" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "JARVIS" -ErrorAction SilentlyContinue | Stop-Process -Force

# Step 2: Clean artifacts
Write-Host "[BUILD] Nettoyage..." -ForegroundColor Cyan
@("$ServerDir\dist", "$ServerDir\build") | ForEach-Object {
    Remove-Item -Path $_ -Recurse -Force -ErrorAction SilentlyContinue
}
Get-Item "$ServerDir\*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

# Step 3: Build Python -> exe
Write-Host "[BUILD] PyInstaller - packaging serveur Python..." -ForegroundColor Cyan
Set-Location $ServerDir
& ".\.venv\Scripts\pip.exe" install pyinstaller -q

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

& ".\.venv\Scripts\pyinstaller.exe" `
    --onefile `
    --name "jarvis-server" `
    --distpath $BinDir `
    --hidden-import="uvicorn.logging" `
    --hidden-import="uvicorn.loops.auto" `
    --hidden-import="uvicorn.lifespan.on" `
    --hidden-import="fastapi" `
    main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] PyInstaller a échoué (code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
Write-Host "[BUILD] [OK] jarvis-server.exe genere dans $BinDir" -ForegroundColor Green

# Step 4: Tauri build
Write-Host "[BUILD] Tauri build release..." -ForegroundColor Cyan
Set-Location $ClientDir
npx tauri build

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Tauri build a échoué (code $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}

Write-Host "[BUILD] [OK] Build termine!" -ForegroundColor Green
Write-Host ("[BUILD] Installeur: " + $ClientDir + "\src-tauri\target\release\bundle") -ForegroundColor Cyan
