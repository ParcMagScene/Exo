# ============================================
#  EXO — Suppression sécurisée du dossier project/
#  Racine officielle : D:/EXO/
# ============================================

$Root = "D:/EXO"
$Project = "D:/EXO/project"

Write-Host "=== Vérification de l'état du projet EXO ===" -ForegroundColor Cyan

# 1) Vérifier que le dossier project existe
if (-Not (Test-Path $Project)) {
    Write-Host "[OK] Le dossier project/ n'existe déjà plus." -ForegroundColor Green
    exit 0
}

# 2) Vérifier que tous les dossiers essentiels existent à la racine
$Expected = @(
    "exo","qml","python","services","scripts",
    "config","logs","models","whispercpp",
    "faiss","cache","docs"
)

$Missing = @()

foreach ($d in $Expected) {
    if (-Not (Test-Path "$Root/$d")) {
        $Missing += $d
    }
}

if ($Missing.Count -gt 0) {
    Write-Host "[ERREUR] Certains dossiers essentiels manquent à la racine :" -ForegroundColor Red
    $Missing | ForEach-Object { Write-Host " - $_" -ForegroundColor Yellow }
    Write-Host "Suppression annulée."
    exit 1
}

Write-Host "[OK] Tous les dossiers essentiels sont présents à la racine." -ForegroundColor Green

# 3) Vérifier que EXO n'utilise plus project/
$Search = Get-ChildItem -Path $Root -Recurse -File |
    Select-String -Pattern "project/" -SimpleMatch

if ($Search) {
    Write-Host "[ERREUR] Des fichiers contiennent encore des références à project/ :" -ForegroundColor Red
    $Search | ForEach-Object { Write-Host " - $($_.Path)" -ForegroundColor Yellow }
    Write-Host "Suppression annulée."
    exit 1
}

Write-Host "[OK] Aucune référence à project/ dans le code." -ForegroundColor Green

# 4) Suppression sécurisée
Write-Host "Suppression du dossier project/..." -ForegroundColor Cyan
Remove-Item -Path $Project -Recurse -Force

if (-Not (Test-Path $Project)) {
    Write-Host "[SUCCÈS] Le dossier project/ a été supprimé proprement." -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Impossible de supprimer project/." -ForegroundColor Red
    exit 1
}

Write-Host "=== Opération terminée ===" -ForegroundColor Cyan
