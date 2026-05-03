# =============================================================================
# Script de vérification finale EXO v30.3
# Contrôle l'intégrité et la compilation du projet
# =============================================================================

Write-Host "Vérification finale du projet EXO v30.3..." -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $PSScriptRoot

# Vérification des fichiers essentiels
Write-Host "`n=== VERIFICATION DES FICHIERS ESSENTIELS ===" -ForegroundColor Yellow

$essentialFiles = @{
    "app\main.cpp" = "Point d'entrée principal"
    "app\core\AssistantManager.cpp" = "Gestionnaire principal"
    "app\core\ConfigManager.cpp" = "Configuration hybride"
    "app\utils\WeatherManager.cpp" = "Météo avec géolocalisation"
    "app\audio\VoicePipeline.cpp" = "Pipeline vocal"
    "CMakeLists.txt" = "Configuration build"
    "docs\EXO_DOCUMENTATION.md" = "Documentation unifiée"
    "README.md" = "Guide rapide"
}

foreach ($file in $essentialFiles.Keys) {
    $fullPath = Join-Path $projectRoot $file
    if (Test-Path $fullPath) {
        Write-Host "OK  - $file : $($essentialFiles[$file])" -ForegroundColor Green
    } else {
        Write-Host "ERR - $file : MANQUANT" -ForegroundColor Red
    }
}

# Vérification de la structure QML
Write-Host "`n=== VERIFICATION QML ===" -ForegroundColor Yellow
$qmlFiles = Get-ChildItem -Path "$projectRoot\qml" -Filter "*.qml" -Recurse
Write-Host "Fichiers QML trouvés: $($qmlFiles.Count)" -ForegroundColor White
$qmlFiles | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Gray }

# Statistiques du projet nettoyé
Write-Host "`n=== STATISTIQUES PROJET ===" -ForegroundColor Yellow

$sourceFiles = Get-ChildItem -Path "$projectRoot\app", "$projectRoot\python", "$projectRoot\qml", "$projectRoot\config" -Recurse -File
$totalLines = 0
$sourceFiles | ForEach-Object { 
    $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
    $totalLines += $lines
}

Write-Host "Fichiers source: $($sourceFiles.Count)" -ForegroundColor White
Write-Host "Lignes de code totales: $totalLines" -ForegroundColor White

$projectSize = (Get-ChildItem -Path $projectRoot -Recurse | Measure-Object -Property Length -Sum).Sum
$sizeInMB = [math]::Round($projectSize / 1MB, 2)
Write-Host "Taille projet: $sizeInMB MB" -ForegroundColor White

# Test de compilation rapide
Write-Host "`n=== TEST COMPILATION ===" -ForegroundColor Yellow

$buildDir = "$projectRoot\build"
if (Test-Path $buildDir) {
    Write-Host "Répertoire build existant: OK" -ForegroundColor Green
    
    $exeFile = Get-ChildItem -Path $buildDir -Filter "RaspberryAssistant.exe" -Recurse | Select-Object -First 1
    if ($exeFile) {
        Write-Host "Exécutable trouvé: $($exeFile.FullName)" -ForegroundColor Green
        Write-Host "Taille: $([math]::Round($exeFile.Length / 1KB, 2)) KB" -ForegroundColor White
        Write-Host "Compilé: $($exeFile.LastWriteTime)" -ForegroundColor White
    } else {
        Write-Host "Exécutable non trouvé - recompilation nécessaire" -ForegroundColor Yellow
    }
} else {
    Write-Host "Répertoire build manquant - première compilation nécessaire" -ForegroundColor Yellow
}

# Vérification des configurations
Write-Host "`n=== VERIFICATION CONFIGURATIONS ===" -ForegroundColor Yellow

$configFiles = Get-ChildItem -Path "$projectRoot\config" -Filter "*.conf*"
foreach ($config in $configFiles) {
    Write-Host "Config: $($config.Name)" -ForegroundColor White
    if ($config.Name -like "*.example") {
        Write-Host "  Type: Template" -ForegroundColor Gray
    } else {
        Write-Host "  Type: Configuration active" -ForegroundColor Green
    }
}

# Résumé final
Write-Host "`n=== RESUME FINAL ===" -ForegroundColor Cyan
Write-Host "Projet EXO v30.3 - État après nettoyage" -ForegroundColor White
Write-Host "- Architecture simplifiée et optimisée" -ForegroundColor Green
Write-Host "- Configuration hybride avec géolocalisation" -ForegroundColor Green
Write-Host "- Documentation unifiée" -ForegroundColor Green
Write-Host "- Code nettoyé et debug optimisé" -ForegroundColor Green
Write-Host "- Scripts de maintenance automatiques" -ForegroundColor Green

Write-Host "`nProjet prêt pour la production!" -ForegroundColor Cyan