# Script de migration EXO vers project/
# Ce script copie tous les dossiers/fichiers hors project/ dans project/ et journalise les opérations.
# À exécuter depuis D:/EXO/

$LogFile = "project/logs/migration.log"
$ProjectRoot = "project"

function Log-Migration {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp`t$Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

function Copy-IfNeeded {
    param([string]$Source, [string]$Target)
    if (!(Test-Path $Target)) {
        $parent = Split-Path $Target -Parent
        if (!(Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item $Source -Destination $Target -Recurse -Force
        if (Test-Path $Target) {
            Log-Migration "SUCCESS: Copied $Source -> $Target"
        } else {
            Log-Migration "ERROR: Failed to copy $Source -> $Target"
        }
    } else {
        Log-Migration "SKIP: $Target already exists"
    }
}

# 1. cache
Copy-IfNeeded "D:/EXO/cache" "$ProjectRoot/cache"
# 2. config
Copy-IfNeeded "D:/EXO/config" "$ProjectRoot/config"
# 3. exo_launcher.ps1
Copy-IfNeeded "D:/EXO/exo_launcher.ps1" "$ProjectRoot/exo_launcher.ps1"
# 4. faiss
Copy-IfNeeded "D:/EXO/faiss" "$ProjectRoot/faiss"
# 5. files
Copy-IfNeeded "D:/EXO/files" "$ProjectRoot/files"
# 6. logs
Copy-IfNeeded "D:/EXO/logs" "$ProjectRoot/logs"
# 7. models
Copy-IfNeeded "D:/EXO/models" "$ProjectRoot/models"
# 8. pip_exo.log
Copy-IfNeeded "D:/EXO/pip_exo.log" "$ProjectRoot/pip_exo.log"
# 9. robocopy_stt_tts.log
Copy-IfNeeded "D:/EXO/robocopy_stt_tts.log" "$ProjectRoot/robocopy_stt_tts.log"
# 10. venv
Copy-IfNeeded "D:/EXO/venv" "$ProjectRoot/venv"
# 11. whispercpp
Copy-IfNeeded "D:/EXO/whispercpp" "$ProjectRoot/whispercpp"

Log-Migration "Migration script completed. Vérifiez les copies avant suppression des originaux."
