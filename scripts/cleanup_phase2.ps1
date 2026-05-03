#!/usr/bin/env powershell
# ============================================================================
# cleanup_phase2.ps1 — Nettoyage du depot EXO (Phase 2)
#
# Usage:
#   .\scripts\cleanup_phase2.ps1          # Execute le nettoyage
#   .\scripts\cleanup_phase2.ps1 -DryRun  # Simule sans modifier
# ============================================================================

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

Write-Host ""
Write-Host "=== EXO Cleanup Phase 2 ===" -ForegroundColor Cyan
if ($DryRun) { Write-Host "[DRY-RUN] Aucune modification ne sera effectuee" -ForegroundColor Yellow }

# --- 1. Supprimer __pycache__ (source uniquement, pas les venvs) ---
Write-Host ""
Write-Host "[1/6] Suppression __pycache__..." -ForegroundColor Green
$pycacheDirs = Get-ChildItem -Path $Root -Recurse -Directory -Filter "__pycache__" |
    Where-Object { $_.FullName -notlike "*\.venv*" -and $_.FullName -notlike "*node_modules*" }

foreach ($d in $pycacheDirs) {
    Write-Host "  DEL $($d.FullName)"
    if (-not $DryRun) { Remove-Item $d.FullName -Recurse -Force }
}
Write-Host "  -> $($pycacheDirs.Count) directories removed"

# --- 2. Supprimer .pytest_cache ---
Write-Host ""
Write-Host "[2/6] Suppression .pytest_cache..." -ForegroundColor Green
$pytestCache = Join-Path $Root ".pytest_cache"
if (Test-Path $pytestCache) {
    Write-Host "  DEL $pytestCache"
    if (-not $DryRun) { Remove-Item $pytestCache -Recurse -Force }
    Write-Host "  -> Removed"
} else {
    Write-Host "  -> Already clean"
}

# --- 3. Supprimer les repertoires vides ---
Write-Host ""
Write-Host "[3/6] Suppression repertoires vides..." -ForegroundColor Green
$emptyDirs = @(
    "qml\components",
    "qml\modules"
)
foreach ($rel in $emptyDirs) {
    $full = Join-Path $Root $rel
    if (Test-Path $full) {
        $children = Get-ChildItem $full -ErrorAction SilentlyContinue
        if (-not $children) {
            Write-Host "  DEL $full (vide)"
            if (-not $DryRun) { Remove-Item $full -Force }
        } else {
            Write-Host "  SKIP $full (contient des fichiers)"
        }
    }
}

# --- 4. Supprimer test_whisper_direct.py (ignore dans pyproject.toml) ---
Write-Host ""
Write-Host "[4/6] Suppression test_whisper_direct.py..." -ForegroundColor Green
$whisperTest = Join-Path $Root "tests\python\test_whisper_direct.py"
if (Test-Path $whisperTest) {
    Write-Host "  DEL $whisperTest"
    if (-not $DryRun) { Remove-Item $whisperTest -Force }
    Write-Host "  -> Removed"
} else {
    Write-Host "  -> Already removed"
}

# --- 5. Archiver les fichiers MD de la racine ---
Write-Host ""
Write-Host "[5/6] Suppression fichiers MD archives (copies dans docs/ARCHIVES.md)..." -ForegroundColor Green
$archivedMDs = @(
    "AutomatisationDocCleanUp.md",
    "Nettoyage.md",
    "RefactoringMassif.md",
    "INTEGRATION XTTS v2 DIRECTML.md",
    [System.Text.Encoding]::UTF8.GetString([byte[]]@(0x49,0x4E,0x54,0xC3,0x89,0x47,0x52,0x41,0x54,0x49,0x4F,0x4E,0x20,0x58,0x54,0x54,0x53,0x20,0x76,0x32,0x20,0x44,0x49,0x52,0x45,0x43,0x54,0x4D,0x4C,0x2E,0x6D,0x64))
)
foreach ($md in $archivedMDs) {
    $full = Join-Path $Root $md
    if (Test-Path $full) {
        Write-Host "  DEL $full"
        if (-not $DryRun) { Remove-Item $full -Force }
    }
}

# --- 6. Supprimer dossiers AppData vides ---
Write-Host ""
Write-Host "[6/6] Nettoyage AppData..." -ForegroundColor Green
$appDataDirs = @(
    "$env:LOCALAPPDATA\EXO",
    "$env:LOCALAPPDATA\EXOAssistant"
)
foreach ($d in $appDataDirs) {
    if (Test-Path $d) {
        $children = Get-ChildItem $d -ErrorAction SilentlyContinue
        if (-not $children) {
            Write-Host "  DEL $d (vide)"
            if (-not $DryRun) { Remove-Item $d -Force }
        } else {
            Write-Host "  SKIP $d (non vide)"
        }
    }
}

# --- Resume ---
Write-Host ""
Write-Host "=== Nettoyage Phase 2 done ===" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "DRY-RUN mode - no changes made. Re-run without -DryRun to execute." -ForegroundColor Yellow
}
