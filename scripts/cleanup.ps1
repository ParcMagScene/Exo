# =============================================================================
# Script de nettoyage EXO v30.3
# Supprime les fichiers temporaires et optimise le projet
# =============================================================================

Write-Host "Nettoyage du projet EXO..." -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $PSScriptRoot

# Nettoyage des dossiers de build temporaires
$buildDirs = @("$projectRoot\build", "$projectRoot\debug", "$projectRoot\release")
foreach ($dir in $buildDirs) {
    if (Test-Path $dir) {
        Write-Host "Nettoyage: $dir" -ForegroundColor Yellow
        Get-ChildItem $dir -Recurse | Where-Object { 
            $_.Extension -in @('.obj', '.pdb', '.ilk', '.tlog', '.tmp') -or
            $_.Name -like '*.vcxproj.user'
        } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        
        # Garde les exécutables mais supprime les fichiers temporaires MSVC
        Get-ChildItem "$dir" -Name "*.exe" | ForEach-Object {
            Write-Host "  Conserve: $_" -ForegroundColor Green
        }
    }
}

# Suppression des fichiers de logs anciens
$logFiles = Get-ChildItem -Path $projectRoot -Filter "*.log" -Recurse
if ($logFiles.Count -gt 0) {
    Write-Host "Suppression de $($logFiles.Count) fichiers de logs" -ForegroundColor Yellow
    $logFiles | Remove-Item -Force
}

# Nettoyage du cache Qt
$qtCache = "$projectRoot\build\.qt"
if (Test-Path $qtCache) {
    Write-Host "Nettoyage du cache Qt" -ForegroundColor Yellow
    Get-ChildItem $qtCache -Recurse | Where-Object { 
        $_.Extension -in @('.tmp', '.cache') 
    } | Remove-Item -Force -ErrorAction SilentlyContinue
}

# Vérification de l'intégrité des fichiers principaux
$essentialFiles = @(
    "$projectRoot\app\main.cpp",
    "$projectRoot\CMakeLists.txt",
    "$projectRoot\docs\EXO_DOCUMENTATION.md",
    "$projectRoot\README.md"
)

$missingFiles = @()
foreach ($file in $essentialFiles) {
    if (-not (Test-Path $file)) {
        $missingFiles += $file
    }
}

if ($missingFiles.Count -eq 0) {
    Write-Host "Tous les fichiers essentiels sont présents" -ForegroundColor Green
} else {
    Write-Host "Fichiers manquants:" -ForegroundColor Red
    $missingFiles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

# Rapport de nettoyage
Write-Host "`nNettoyage terminé!" -ForegroundColor Cyan
Write-Host "   - Fichiers temporaires supprimés" -ForegroundColor White
Write-Host "   - Cache Qt optimisé" -ForegroundColor White
Write-Host "   - Logs anciens nettoyés" -ForegroundColor White
Write-Host "   - Structure de projet vérifiée" -ForegroundColor White

# Affichage de la taille du projet
$projectSize = (Get-ChildItem -Path $projectRoot -Recurse | Measure-Object -Property Length -Sum).Sum
$sizeInMB = [math]::Round($projectSize / 1MB, 2)
Write-Host "Taille totale du projet: $sizeInMB MB" -ForegroundColor Cyan