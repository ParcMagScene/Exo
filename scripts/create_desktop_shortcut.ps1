#!/usr/bin/env powershell
# Crée un raccourci "EXO Assistant" sur le Bureau Windows.
# Usage : powershell -ExecutionPolicy Bypass -File scripts\create_desktop_shortcut.ps1

$projectDir = (Resolve-Path "$PSScriptRoot\..").Path
$desktop    = [Environment]::GetFolderPath('Desktop')
$lnkPath    = Join-Path $desktop "EXO Assistant.lnk"

$launcher   = Join-Path $projectDir "launch_exo_silent.ps1"

if (-not (Test-Path $launcher)) {
    Write-Host "ERREUR: launch_exo_silent.ps1 introuvable : $launcher" -ForegroundColor Red
    exit 1
}

$shell    = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)

$icoPath = Join-Path $projectDir "resources\icons\exo.ico"

$shortcut.TargetPath       = "powershell.exe"
$shortcut.Arguments        = "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description      = "Lance EXO Assistant (silencieux)"
if (Test-Path $icoPath) {
    $shortcut.IconLocation = "$icoPath,0"
}
$shortcut.Save()

Write-Host "Raccourci cree : $lnkPath" -ForegroundColor Green
