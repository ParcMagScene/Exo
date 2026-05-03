#!/usr/bin/env powershell
# Script de lancement EXO Assistant
# ⚠️  DEPRECATED: Prefer VS Code tasks (launch_all) for development.
#     This standalone script is kept for CI/headless use only.
# Utilisation: .\launch_exo.ps1
# Multi-GPU: AMD = GUI | RTX 3070 = compute IA (CUDA + Vulkan)

Write-Host "Lancement d'EXO Assistant..." -ForegroundColor Cyan
Write-Host "=== Configuration Multi-GPU ===" -ForegroundColor Magenta
Write-Host "  GUI (Qt/QML)  : AMD (affichage)" -ForegroundColor Green
Write-Host "  TTS (CosyVoice2): CUDA -> RTX 3070" -ForegroundColor Green
Write-Host "  STT (Whisper)  : Vulkan -> RTX 3070" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Magenta

# --- Racines projet ---
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ssdRoot    = if ($env:EXO_ROOT) { $env:EXO_ROOT } else { "D:\EXO" }
$pythonSTT  = "$projectDir\.venv_stt_tts\Scripts\python.exe"

# --- PYTHONPATH (requis par shared/, tts/, stt/, etc.) ---
$env:PYTHONPATH = "$projectDir\python"

# --- Dossier logs ---
$logDir = "$ssdRoot\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# --- Idempotence: tuer les anciennes instances de launch_exo.ps1 (zombies tenant un Tee-Object) ---
$selfPid = $PID
$oldLaunchers = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessId -ne $selfPid -and $_.CommandLine -match 'launch_exo\.ps1' }
foreach ($p in $oldLaunchers) {
    Write-Host "Nettoyage ancien launcher PID $($p.ProcessId) (zombie tenant exo_console.log)..." -ForegroundColor Yellow
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
if ($oldLaunchers) { Start-Sleep -Seconds 2 }

# --- Rotation exo_console.log si verrouille ou volumineux ---
$consoleLog = "$logDir\exo_console.log"
if (Test-Path $consoleLog) {
    $locked = $false
    try {
        $fs = [System.IO.File]::Open($consoleLog, 'Open', 'ReadWrite', 'None')
        $fs.Close()
    } catch { $locked = $true }
    $sizeMB = (Get-Item $consoleLog).Length / 1MB
    if ($locked -or $sizeMB -gt 50) {
        $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $rotated = "$logDir\exo_console_$stamp.log"
        try {
            Move-Item $consoleLog $rotated -Force -ErrorAction Stop
            Write-Host "exo_console.log $(if($locked){'verrouille'}else{'volumineux'}) -> rotation vers $(Split-Path $rotated -Leaf)" -ForegroundColor Yellow
        } catch {
            Write-Host "Impossible de rotater exo_console.log (toujours verrouille): $_" -ForegroundColor Red
            Write-Host "Verifiez les processus tenant le fichier puis relancez." -ForegroundColor Red
            exit 1
        }
    }
}

function Wait-ForServicePort {
    param(
        [Parameter(Mandatory=$true)][string]$ServiceName,
        [Parameter(Mandatory=$true)][int]$Port,
        [Parameter(Mandatory=$true)]$Process,
        [Parameter(Mandatory=$true)][string]$ErrorLog,
        [int]$TimeoutSeconds = 30,
        [int]$PollSeconds = 1
    )

    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        if ($Process -and $Process.HasExited) {
            Write-Host "ERREUR: $ServiceName s'est arrete avant d'ouvrir le port $Port (code $($Process.ExitCode))." -ForegroundColor Red
            if (Test-Path $ErrorLog) {
                Write-Host "Dernieres lignes de $ErrorLog :" -ForegroundColor Yellow
                Get-Content $ErrorLog -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
            }
            return $false
        }

        $listening = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq 'Listen' }
        if ($listening) {
            Write-Host "$ServiceName pret sur le port $Port" -ForegroundColor Green
            return $true
        }

        Start-Sleep -Seconds $PollSeconds
        $elapsed += $PollSeconds
    }

    Write-Host "ERREUR: $ServiceName n'a pas demarre dans les ${TimeoutSeconds}s." -ForegroundColor Red
    if ($Process -and -not $Process.HasExited) {
        Write-Host "$ServiceName est toujours vivant (PID: $($Process.Id)) mais le port $Port n'est pas ouvert." -ForegroundColor Yellow
    }
    if (Test-Path $ErrorLog) {
        Write-Host "Dernieres lignes de $ErrorLog :" -ForegroundColor Yellow
        Get-Content $ErrorLog -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
    }
    return $false
}

function Wait-ForServiceHealth {
    param(
        [Parameter(Mandatory=$true)][string]$ServiceName,
        [Parameter(Mandatory=$true)][string]$HealthUrl,
        [Parameter(Mandatory=$true)]$Process,
        [Parameter(Mandatory=$true)][string]$ErrorLog,
        [int]$TimeoutSeconds = 90,
        [int]$PollSeconds = 2
    )

    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        if ($Process -and $Process.HasExited) {
            Write-Host "ERREUR: $ServiceName s'est arrete avant /health (code $($Process.ExitCode))." -ForegroundColor Red
            if (Test-Path $ErrorLog) {
                Get-Content $ErrorLog -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
            }
            return $false
        }
        try {
            $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                Write-Host "$ServiceName /health OK : $($resp.Content)" -ForegroundColor Green
                return $true
            }
        } catch {
            # not ready yet
        }
        Start-Sleep -Seconds $PollSeconds
        $elapsed += $PollSeconds
    }

    Write-Host "ERREUR: $ServiceName /health KO apres ${TimeoutSeconds}s." -ForegroundColor Red
    if (Test-Path $ErrorLog) {
        Get-Content $ErrorLog -Tail 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
    }
    return $false
}

# --- TTS GPU CUDA (RTX 3070) ---
# Pipeline TTS : selectionnable via $env:EXO_TTS_ENGINE
#   "cosyvoice" (defaut) -> python/tts/tts_server_streaming.py (.venv_stt_tts)
#   "orpheus"            -> services/orpheus/server_ws.py     (services/orpheus/venv)
# Les deux exposent le MEME protocole WS sur le MEME port (8767) + /health HTTP.
$ttsPort = 8767
$ttsEngine = ($env:EXO_TTS_ENGINE | ForEach-Object { $_.ToLower() })
if (-not $ttsEngine) { $ttsEngine = 'cosyvoice' }

$ttsRunning = Get-NetTCPConnection -LocalPort $ttsPort -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq 'Listen' }
if (-not $ttsRunning) {
    if ($ttsEngine -eq 'orpheus') {
        $ttsScript = "$projectDir\services\orpheus\server_ws.py"
        $ttsPython = "$projectDir\services\orpheus\venv\Scripts\python.exe"
        $ttsLabel  = "Orpheus 3B FR (GGUF Q8) CUDA"
        # Timeout : load LLM ~3s + SNAC ~2s + warmup ~5s + marge => 60s.
        $ttsTimeout = 60
    } else {
        $ttsScript = "$projectDir\python\tts\tts_server_streaming.py"
        $ttsPython = $pythonSTT
        $ttsLabel  = "CosyVoice2 CUDA - RTX 3070"
        # Timeout : 35s load CosyVoice2 + 10s warmup + marge => 90s.
        $ttsTimeout = 90
    }
    if ((Test-Path $ttsPython) -and (Test-Path $ttsScript)) {
        Write-Host "Demarrage TTS streaming ($ttsLabel)..." -ForegroundColor Yellow
        $ttsStdout = "$logDir\tts_server.log"
        $ttsStderr = "$logDir\tts_server.err.log"
        $ttsArgs = "$ttsScript --host 0.0.0.0 --port $ttsPort"
        $ttsProc = Start-Process -FilePath $ttsPython `
            -ArgumentList $ttsArgs `
            -PassThru -WindowStyle Minimized `
            -RedirectStandardOutput $ttsStdout `
            -RedirectStandardError $ttsStderr
        Write-Host "TTS streaming lance (PID: $($ttsProc.Id)) - attente /health..." -ForegroundColor Yellow
        $ttsReady = Wait-ForServiceHealth `
            -ServiceName "TTS streaming" `
            -HealthUrl "http://127.0.0.1:$ttsPort/health" `
            -Process $ttsProc -ErrorLog $ttsStderr `
            -TimeoutSeconds $ttsTimeout -PollSeconds 2
        if (-not $ttsReady) {
            Write-Host "ATTENTION: TTS streaming non operationnel - fallback Qt TTS" -ForegroundColor Red
        }
    } else {
        Write-Host "ATTENTION: TTS streaming non disponible - EXO utilisera le fallback Qt TTS" -ForegroundColor Red
    }
} else {
    Write-Host "TTS streaming deja actif sur le port $ttsPort" -ForegroundColor Green
}

# Verifier que l'executable existe
$exePath = "$projectDir\build\Release\RaspberryAssistant.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "Erreur: Executable non trouve a $exePath" -ForegroundColor Red
    Write-Host "Compilez d'abord avec: cmake --build build --config Release" -ForegroundColor Yellow
    exit 1
}

# S'assurer que le runtime Qt est resolvable.
# Priorite:
#  1) DLL Qt deja deployeees a cote de l'executable
#  2) variable d'environnement QT_BIN_PATH
#  3) detection automatique dans C:\Qt\*\msvc2022_64\bin
$exeDir = Split-Path -Parent $exePath
$bundledQtCore = Join-Path $exeDir "Qt6Core.dll"

if (Test-Path $bundledQtCore) {
    if ($env:PATH -notlike "*$exeDir*") {
        Write-Host "Runtime Qt deja deploye a cote de l'executable" -ForegroundColor Green
        $env:PATH = "$exeDir;$env:PATH"
    }
} else {
    $qtCandidates = @()
    if ($env:QT_BIN_PATH) {
        $qtCandidates += $env:QT_BIN_PATH
    }
    $qtCandidates += Get-ChildItem "C:\Qt" -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "msvc2022_64\bin" }

    $qtPath = $qtCandidates |
        Where-Object { $_ -and (Test-Path (Join-Path $_ "Qt6Core.dll")) } |
        Select-Object -First 1

    if (-not $qtPath) {
        Write-Host "Erreur: runtime Qt introuvable. Definissez QT_BIN_PATH ou redeployez les DLL Qt dans $exeDir" -ForegroundColor Red
        exit 1
    }

    if ($env:PATH -notlike "*$qtPath*") {
        Write-Host "Ajout du PATH Qt: $qtPath" -ForegroundColor Yellow
        $env:PATH = "$qtPath;$env:PATH"
    }
}

# --- Variables d'environnement EXO (chemins SSD) ---
$env:EXO_SSD_ROOT        = $ssdRoot
$env:EXO_WHISPER_MODELS = "$ssdRoot\models\whisper"
$env:EXO_WHISPERCPP_BIN = "$ssdRoot\whispercpp\build_vk\bin\Release"
$env:EXO_COSYVOICE_MODELS = "$ssdRoot\models\cosyvoice_fr"
$env:EXO_FAISS_DIR      = "$ssdRoot\faiss\semantic_memory"
$env:EXO_WAKEWORD_MODELS = "$ssdRoot\models\wakeword"
$env:EXO_FILES_DIR       = "$ssdRoot\files"
$env:HF_HOME            = "$ssdRoot\cache\huggingface"
$env:TRANSFORMERS_CACHE  = "$ssdRoot\cache\huggingface\hub"
$env:TORCH_HOME          = "$ssdRoot\cache\torch"
Write-Host "Variables EXO configurees (SSD: $ssdRoot)" -ForegroundColor Green

# Charger les variables d'environnement depuis .env
$envFile = "$projectDir\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host "Variables d'environnement chargees depuis .env" -ForegroundColor Green
} else {
    Write-Host "Attention: fichier .env non trouve. Copiez .env.example en .env" -ForegroundColor Yellow
}

# Lancer le serveur STT (whisper.cpp) en arriere-plan
$sttServer = "$projectDir\python\stt\stt_server.py"

$sttRunning = Get-NetTCPConnection -LocalPort 8766 -ErrorAction SilentlyContinue
if (-not $sttRunning) {
    if (Test-Path $pythonSTT) {
        Write-Host "Demarrage du serveur STT (whisper.cpp medium — Vulkan GPU)..." -ForegroundColor Yellow
        $sttStdout = "$logDir\stt_stdout.log"
        $sttStderr = "$logDir\stt_stderr.log"
        $sttProc = Start-Process -FilePath $pythonSTT -ArgumentList "$sttServer --backend whispercpp --model small --beam-size 1 --language fr --device vulkan" -PassThru -WindowStyle Minimized -RedirectStandardOutput $sttStdout -RedirectStandardError $sttStderr
        Write-Host "STT server lance (PID: $($sttProc.Id)) - attente connexion..." -ForegroundColor Yellow
        $sttReady = Wait-ForServicePort -ServiceName "STT server" -Port 8766 -Process $sttProc -ErrorLog $sttStderr -TimeoutSeconds 30 -PollSeconds 1
        if (-not $sttReady) {
            Write-Host "Attention: STT server indisponible - la reconnaissance vocale sera degradee" -ForegroundColor Red
        }
    } else {
        Write-Host "Attention: Python venv non trouve ($pythonSTT) - STT server non lance" -ForegroundColor Red
    }
} else {
    Write-Host "STT server deja en cours sur le port 8766" -ForegroundColor Green
}

# --- Venv principal (orchestrateur + services web) ---
$pythonVenv = "$projectDir\.venv\Scripts\python.exe"
# S'assurer que PYTHONPATH est defini pour tous les sous-processus
$env:PYTHONPATH = "$projectDir\python"

function Start-EXOService {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Script,
        [Parameter(Mandatory=$true)][int]$Port,
        [Parameter(Mandatory=$true)][string]$Python,
        [string[]]$ExtraArgs = @(),
        [int]$Timeout = 0
    )
    $running = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq 'Listen' }
    if ($running) {
        Write-Host "$Name deja actif sur le port $Port" -ForegroundColor Green
        return $null
    }
    if (-not (Test-Path $Python)) {
        Write-Host "ATTENTION: Python introuvable pour $Name ($Python)" -ForegroundColor Red
        return $null
    }
    $fullScript = "$projectDir\$Script"
    $argStr = if ($ExtraArgs.Count -gt 0) { "$fullScript $($ExtraArgs -join ' ')" } else { $fullScript }
    $stdout = "$logDir\$($Name.ToLower())_stdout.log"
    $stderr = "$logDir\$($Name.ToLower())_stderr.log"
    $proc = Start-Process -FilePath $Python -ArgumentList $argStr -PassThru -WindowStyle Minimized `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-Host "$Name lance (PID: $($proc.Id))" -ForegroundColor Yellow
    if ($Timeout -gt 0) {
        $ok = Wait-ForServicePort -ServiceName $Name -Port $Port -Process $proc -ErrorLog $stderr `
            -TimeoutSeconds $Timeout -PollSeconds 1
        if (-not $ok) {
            Write-Host "ATTENTION: $Name non disponible apres ${Timeout}s" -ForegroundColor Red
        }
    }
    return $proc
}

# --- Services critiques (attente avant lancement C++) ---
Write-Host "`n--- Demarrage services critiques ---" -ForegroundColor Cyan
$orcProc = Start-EXOService -Name "Orchestrateur" -Script "python/orchestrator/exo_server.py"       -Port 8765 -Python $pythonVenv  -Timeout 60
$memProc = Start-EXOService -Name "Memory"        -Script "python/memory/memory_server.py"          -Port 8771 -Python $pythonSTT   -Timeout 30
$ctxProc = Start-EXOService -Name "Context"       -Script "python/context/context_engine.py"        -Port 8777 -Python $pythonSTT   -Timeout 30
$plnProc = Start-EXOService -Name "Planner"       -Script "python/planner/task_planner_server.py"   -Port 8778 -Python $pythonSTT   -Timeout 30
$excProc = Start-EXOService -Name "Executor"      -Script "python/executor/task_executor_server.py" -Port 8779 -Python $pythonSTT   -Timeout 30
$verProc = Start-EXOService -Name "Verifier"      -Script "python/verifier/task_verifier_server.py" -Port 8780 -Python $pythonSTT   -Timeout 30
$sysProc = Start-EXOService -Name "System"        -Script "python/tools/system_service.py"           -Port 8783 -Python $pythonSTT   -Timeout 30

# --- Services lazy (arriere-plan, pas d'attente) ---
Write-Host "`n--- Demarrage services lazy ---" -ForegroundColor Cyan
$nluProc  = Start-EXOService -Name "NLU"       -Script "python/nlu/nlu_server.py"               -Port 8772 -Python $pythonSTT
$vadProc  = Start-EXOService -Name "VAD"       -Script "python/vad/vad_server.py"               -Port 8768 -Python $pythonSTT
$wwProc   = Start-EXOService -Name "Wakeword"  -Script "python/wakeword/wakeword_server.py"     -Port 8770 -Python $pythonSTT
$toolsProc= Start-EXOService -Name "Tools"     -Script "python/tools/tools_server.py"           -Port 8776 -Python $pythonVenv
$wsProc   = Start-EXOService -Name "Websearch" -Script "python/websearch/websearch_server.py"   -Port 8773 -Python $pythonVenv
$newsProc = Start-EXOService -Name "News"      -Script "python/news/news_server.py"             -Port 8774 -Python $pythonVenv
$knowProc = Start-EXOService -Name "Knowledge" -Script "python/knowledge/knowledge_server.py"   -Port 8775 -Python $pythonVenv

# Lancer EXO
Write-Host "Demarrage d'EXO..." -ForegroundColor Green
Set-Location "$projectDir\build\Release"
Write-Host "EXO demarre a $(Get-Date -Format 'HH:mm:ss') - logs dans $logDir" -ForegroundColor Cyan
try {
    & .\RaspberryAssistant.exe 2>&1 | Tee-Object -FilePath "$logDir\exo_console.log"
    $exoExitCode = $LASTEXITCODE
} catch {
    Write-Host "Tee-Object a echoue ($($_.Exception.Message)) - relance sans capture console" -ForegroundColor Yellow
    & .\RaspberryAssistant.exe
    $exoExitCode = $LASTEXITCODE
}
Write-Host "EXO termine avec code: $exoExitCode a $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor $(if ($exoExitCode -eq 0) { 'Green' } else { 'Red' })

# Cleanup: arreter les serveurs lances
foreach ($pair in @(
    @("TTS CUDA",    $ttsProc),
    @("STT",         $sttProc),
    @("Orchestrateur",$orcProc),
    @("Memory",      $memProc),
    @("Context",     $ctxProc),
    @("Planner",     $plnProc),
    @("Executor",    $excProc),
    @("Verifier",    $verProc),
    @("System",      $sysProc),
    @("NLU",         $nluProc),
    @("VAD",         $vadProc),
    @("Wakeword",    $wwProc),
    @("Tools",       $toolsProc),
    @("Websearch",   $wsProc),
    @("News",        $newsProc),
    @("Knowledge",   $knowProc)
)) {
    $svcName = $pair[0]; $proc = $pair[1]
    if ($proc -and -not $proc.HasExited) {
        Write-Host "Arret de $svcName (PID: $($proc.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "EXO ferme." -ForegroundColor Cyan