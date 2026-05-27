#Requires -Version 5.1
<#
.SYNOPSIS
    Nettoyage post-build JARVIS - supprime les artefacts temporaires.
#>
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "[CLEAN] Nettoyage artefacts JARVIS..." -ForegroundColor Cyan

$Targets = @(
    "$Root\server\build",
    "$Root\server\dist",
    "$Root\client\src-tauri\target\release\build",
    "$Root\client\src-tauri\target\release\deps",
    "$Root\client\dist"
)

foreach ($target in $Targets) {
    if (Test-Path $target) {
        Remove-Item -Path $target -Recurse -Force
        Write-Host "  Supprimé: $target" -ForegroundColor DarkGray
    }
}

Get-Item "$Root\server\*.spec" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Force
    Write-Host "  Supprimé: $($_.FullName)" -ForegroundColor DarkGray
}

Write-Host "[CLEAN] [OK] Nettoyage terminé." -ForegroundColor Green
