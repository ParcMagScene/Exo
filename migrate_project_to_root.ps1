# Script PowerShell de migration EXO : project/ → racine D:/EXO/
# (Ce script n'est plus nécessaire après migration. À archiver ou supprimer.)
# À exécuter depuis D:/EXO/

$projectRoot = Join-Path $PWD "project"

if (!(Test-Path $projectRoot)) {
    Write-Error "Migration déjà effectuée. Aucun dossier 'project/' à migrer."
    exit 1
}

# Liste tous les fichiers/dossiers à déplacer
$items = Get-ChildItem -Path $projectRoot -Force

foreach ($item in $items) {
    $dest = Join-Path $PWD $item.Name
    if (Test-Path $dest) {
        Write-Host "[INFO] $($item.Name) existe déjà à la racine. Fusion ou écrasement manuel nécessaire si conflit."
    }
    else {
        Move-Item -Path $item.FullName -Destination $PWD -Force
        Write-Host "[OK] Déplacé : $($item.Name)"
    }
}

# (Plus d'action requise)
if ((Get-ChildItem -Path $projectRoot -Force | Measure-Object).Count -eq 0) {
    Remove-Item -Path $projectRoot -Force
    Write-Host "[OK] Migration déjà effectuée."
} else {
    Write-Warning "Aucune action requise."
}

Write-Host "[FIN] Migration physique terminée. Passez à la mise à jour des chemins dans le code."
