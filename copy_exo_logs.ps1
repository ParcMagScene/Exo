# Script PowerShell : copy_exo_logs.ps1
# Copie tous les fichiers *.log et *.err.log du dossier courant et sous-dossiers vers D:\EXO\logs\
# Usage : .\copy_exo_logs.ps1

$source = Get-Location
$target = "D:/EXO/logs"
if (!(Test-Path $target)) { New-Item -ItemType Directory -Path $target | Out-Null }

# Copie tous les logs (hors D:\EXO\logs déjà)
Get-ChildItem -Path $source -Recurse -Include *.log,*.err.log | Where-Object { $_.FullName -notlike "$target*" } | ForEach-Object {
    $dest = Join-Path $target $_.Name
    Copy-Item $_.FullName $dest -Force
}
Write-Host "Tous les logs ont été copiés dans $target."
