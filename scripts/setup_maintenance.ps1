# ═══════════════════════════════════════════════════════════════
#  EXO - Setup Maintenance Automatique
#  Installe les hooks Git, cree les dossiers, initialise context.md
#
#  Usage: powershell -ExecutionPolicy Bypass -File scripts\setup_maintenance.ps1
# ═══════════════════════════════════════════════════════════════
param(
    [switch]$Force  # Ecraser les hooks existants
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  EXO - Installation maintenance automatique" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# -- 1. Creer les dossiers manquants --
Write-Host "[setup] Creation des dossiers..." -ForegroundColor Yellow
$dirs = @("logs", ".exo_context", "docs/architecture")
foreach ($d in $dirs) {
    $fullPath = Join-Path $Root $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "  + $d/" -ForegroundColor Green
    } else {
        Write-Host "  = $d/ (existe)" -ForegroundColor DarkGray
    }
}

# -- 2. Installer les hooks Git --
Write-Host ""
Write-Host "[setup] Installation des hooks Git..." -ForegroundColor Yellow

$gitHooksDir = Join-Path $Root ".git\hooks"
if (-not (Test-Path $gitHooksDir)) {
    Write-Host "  ERREUR: .git/hooks/ introuvable - verifiez que c'est un depot Git" -ForegroundColor Red
    exit 1
}

$hooks = @("pre-commit", "post-commit")
foreach ($hook in $hooks) {
    $src = Join-Path $Root "scripts\hooks\$hook"
    $dst = Join-Path $gitHooksDir $hook

    if (-not (Test-Path $src)) {
        Write-Host "  ERREUR: $src manquant" -ForegroundColor Red
        continue
    }

    if ((Test-Path $dst) -and -not $Force) {
        Write-Host "  = $hook (existe - utiliser -Force pour ecraser)" -ForegroundColor DarkGray
    } else {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  + $hook installe" -ForegroundColor Green
    }
}

# -- 3. Initialiser context.md --
Write-Host ""
Write-Host "[setup] Initialisation context.md..." -ForegroundColor Yellow

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    # Fallback
    $python = "python"
}

$maintainScript = Join-Path $Root "scripts\auto_maintain.py"
if (Test-Path $maintainScript) {
    & $python $maintainScript context 2>$null
    Write-Host "  + .exo_context/context.md genere" -ForegroundColor Green
} else {
    Write-Host "  WARN: scripts/auto_maintain.py introuvable" -ForegroundColor Yellow
}

# -- 4. Premiere execution documentation --
Write-Host ""
Write-Host "[setup] Generation documentation initiale..." -ForegroundColor Yellow

if (Test-Path $maintainScript) {
    & $python $maintainScript docs 2>$null
    Write-Host "  + Documentation generee" -ForegroundColor Green
}

# -- 5. Resume --
Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  Installation terminee !" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Hooks installes :" -ForegroundColor White
Write-Host "    pre-commit  - formatage, conventions, nettoyage" -ForegroundColor DarkGray
Write-Host "    post-commit - docs auto, CHANGELOG, context.md" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Commandes disponibles :" -ForegroundColor White
Write-Host "    python scripts/auto_maintain.py all     # Maintenance complete" -ForegroundColor DarkGray
Write-Host "    python scripts/auto_maintain.py docs    # Documentation seule" -ForegroundColor DarkGray
Write-Host "    python scripts/auto_maintain.py check   # Verification conventions" -ForegroundColor DarkGray
Write-Host "    python scripts/auto_maintain.py clean   # Nettoyage" -ForegroundColor DarkGray
Write-Host ""
