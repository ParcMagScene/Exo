# =============================================================================
#  launch_exo_silent.ps1 — Lanceur EXO 100 % silencieux (aucune fenetre console)
# =============================================================================
#
#  POLITIQUE STRICTE
#  -----------------
#  Ce script est le SEUL point d'entree autorise pour demarrer EXO.
#  Ne JAMAIS lancer un service Python individuellement (tts_server.py,
#  stt_server.py, observability.py, etc.). Ne JAMAIS ouvrir un terminal.
#
#  RACCOURCI WINDOWS
#  -----------------
#  Cible :
#    powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "D:\EXO\project\launch_exo_silent.ps1"
#  Demarrer dans :
#    D:\EXO\project
#  Executer en :
#    Reduit (le -WindowStyle Hidden masque deja la fenetre).
#
#  COMMANDES DISPONIBLES (en interactif)
#  -------------------------------------
#    . D:\EXO\project\launch_exo_silent.ps1   # dot-source pour exposer les fonctions
#    Start-EXO       # demarre tous les services + GUI (silencieux, non bloquant)
#    Stop-EXO        # arrete proprement tous les processus EXO
#    Restart-EXO     # Stop-EXO puis Start-EXO
#    Get-EXOStatus   # affiche l'etat des ports + PID
#
#  Quand le script est INVOQUE directement (raccourci/double-clic), il execute
#  automatiquement Start-EXO puis se termine, EXO continue en arriere-plan.
# =============================================================================

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# --- Racines ----------------------------------------------------------------
$script:ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $script:ProjectDir) { $script:ProjectDir = 'D:\EXO\project' }
$script:SsdRoot    = if ($env:EXO_ROOT) { $env:EXO_ROOT } else { 'D:\EXO' }
$script:LogDir     = Join-Path $script:SsdRoot 'logs'
$script:LauncherLog = Join-Path $script:LogDir 'launcher.log'
$script:PidStore    = Join-Path $script:LogDir 'exo_pids.json'

if (-not (Test-Path $script:LogDir)) {
    New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
}

# --- Logging ----------------------------------------------------------------
function Write-Launcher {
    param(
        [Parameter(Mandatory)] [string]$Message,
        [ValidateSet('INFO', 'OK', 'WARN', 'FAIL')] [string]$Level = 'INFO'
    )
    $line = "[{0}] [{1,-4}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    try {
        Add-Content -Path $script:LauncherLog -Value $line -Encoding UTF8 -ErrorAction Stop
    } catch {
        # Log indisponible : on ignore silencieusement (politique : aucune fenetre).
    }
}

# --- PID store --------------------------------------------------------------
function Save-EXOPidEntry {
    param([string]$Name, [int]$ProcessId, [int]$Port)
    $store = @{}
    if (Test-Path $script:PidStore) {
        try {
            $raw = Get-Content $script:PidStore -Raw -ErrorAction Stop
            if ($raw) {
                $obj = $raw | ConvertFrom-Json -ErrorAction Stop
                $obj.PSObject.Properties | ForEach-Object { $store[$_.Name] = $_.Value }
            }
        } catch { $store = @{} }
    }
    $store[$Name] = [pscustomobject]@{
        pid       = $ProcessId
        port      = $Port
        started   = (Get-Date -Format 'o')
    }
    ($store | ConvertTo-Json -Depth 4) | Set-Content -Path $script:PidStore -Encoding UTF8
}

function Get-EXOPidStore {
    if (-not (Test-Path $script:PidStore)) { return @{} }
    try {
        $raw = Get-Content $script:PidStore -Raw
        if (-not $raw) { return @{} }
        $obj = $raw | ConvertFrom-Json
        $store = @{}
        $obj.PSObject.Properties | ForEach-Object { $store[$_.Name] = $_.Value }
        return $store
    } catch { return @{} }
}

function Clear-EXOPidStore {
    if (Test-Path $script:PidStore) {
        Remove-Item $script:PidStore -Force -ErrorAction SilentlyContinue
    }
}

# --- Port helpers -----------------------------------------------------------
function Test-PortListening {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-PortReady {
    param(
        [Parameter(Mandatory)] [int]$Port,
        [int]$TimeoutSeconds = 10,
        [int]$PollMs = 250
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening -Port $Port) { return $true }
        Start-Sleep -Milliseconds $PollMs
    }
    return $false
}

# --- Hidden process launch --------------------------------------------------
function Start-EXOHiddenProcess {
    <#
    Lance un processus en arriere-plan, COMPLETEMENT masque (WindowStyle Hidden
    + CreateNoWindow simule via redirection des flux). Retourne l'objet Process.
    #>
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory)] [string]$StdoutLog,
        [Parameter(Mandatory)] [string]$StderrLog,
        [string]$WorkingDirectory = $script:ProjectDir
    )
    # On purge les anciens logs pour eviter une croissance infinie entre les runs.
    foreach ($f in @($StdoutLog, $StderrLog)) {
        if (Test-Path $f) {
            try { Clear-Content $f -ErrorAction Stop } catch {}
        }
    }
    $params = @{
        FilePath               = $FilePath
        WindowStyle            = 'Hidden'
        PassThru               = $true
        WorkingDirectory       = $WorkingDirectory
        RedirectStandardOutput = $StdoutLog
        RedirectStandardError  = $StderrLog
    }
    if ($ArgumentList.Count -gt 0) { $params.ArgumentList = $ArgumentList }
    return Start-Process @params
}

# --- Service descriptor -----------------------------------------------------
function Start-EXOService {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Python,
        [Parameter(Mandatory)] [string]$Script,
        [Parameter(Mandatory)] [int]$Port,
        [string[]]$ExtraArgs = @(),
        [int]$HealthTimeoutSeconds = 10
    )
    $stdout = Join-Path $script:LogDir ("{0}.log"     -f $Name.ToLower())
    $stderr = Join-Path $script:LogDir ("{0}.err.log" -f $Name.ToLower())

    if (Test-PortListening -Port $Port) {
        Write-Launcher "$Name deja actif sur le port $Port (skip)" -Level 'INFO'
        return
    }
    if (-not (Test-Path $Python)) {
        Write-Launcher "$Name : interpreteur Python introuvable ($Python)" -Level 'FAIL'
        return
    }
    $scriptPath = Join-Path $script:ProjectDir $Script
    if (-not (Test-Path $scriptPath)) {
        Write-Launcher "$Name : script introuvable ($scriptPath)" -Level 'FAIL'
        return
    }

    $argList = @($scriptPath) + $ExtraArgs
    try {
        $proc = Start-EXOHiddenProcess `
            -FilePath  $Python `
            -ArgumentList $argList `
            -StdoutLog $stdout `
            -StderrLog $stderr
    } catch {
        Write-Launcher "$Name : echec du lancement ($($_.Exception.Message))" -Level 'FAIL'
        return
    }

    Save-EXOPidEntry -Name $Name -ProcessId $proc.Id -Port $Port
    Write-Launcher "$Name lance (PID $($proc.Id), port $Port)" -Level 'INFO'

    if ($HealthTimeoutSeconds -gt 0) {
        if (Wait-PortReady -Port $Port -TimeoutSeconds $HealthTimeoutSeconds) {
            Write-Launcher "$Name ready" -Level 'OK'
        } else {
            Write-Launcher "$Name timeout (port $Port pas pret en ${HealthTimeoutSeconds}s)" -Level 'FAIL'
        }
    }
}

# ===========================================================================
#  Start-EXO
# ===========================================================================
function Start-EXO {
    [CmdletBinding()]
    param()

    Write-Launcher "================ Start-EXO ================" -Level 'INFO'
    Write-Launcher "ProjectDir = $script:ProjectDir"             -Level 'INFO'
    Write-Launcher "SsdRoot    = $script:SsdRoot"                -Level 'INFO'

    # --- Variables d'environnement EXO --------------------------------------
    $env:PYTHONPATH            = Join-Path $script:ProjectDir 'python'
    $env:EXO_SSD_ROOT          = $script:SsdRoot
    $env:EXO_WHISPER_MODELS    = Join-Path $script:SsdRoot 'models\whisper'
    $env:EXO_WHISPERCPP_BIN    = Join-Path $script:SsdRoot 'whispercpp\build_vk\bin\Release'
    $env:EXO_COSYVOICE_MODELS  = Join-Path $script:SsdRoot 'models\cosyvoice_fr'
    $env:EXO_FAISS_DIR         = Join-Path $script:SsdRoot 'faiss\semantic_memory'
    $env:EXO_WAKEWORD_MODELS   = Join-Path $script:SsdRoot 'models\wakeword'
    $env:EXO_FILES_DIR         = Join-Path $script:SsdRoot 'files'
    $env:HF_HOME               = Join-Path $script:SsdRoot 'cache\huggingface'
    $env:TRANSFORMERS_CACHE    = Join-Path $script:SsdRoot 'cache\huggingface\hub'
    $env:TORCH_HOME            = Join-Path $script:SsdRoot 'cache\torch'

    # Charge .env si present
    $envFile = Join-Path $script:ProjectDir '.env'
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                [System.Environment]::SetEnvironmentVariable(
                    $matches[1].Trim(), $matches[2].Trim(), 'Process')
            }
        }
        Write-Launcher ".env charge" -Level 'INFO'
    }

    # --- Ne pas relancer si EXO tourne deja ---------------------------------
    if (Test-PortListening -Port 8765) {
        Write-Launcher "Orchestrateur deja actif (port 8765) - Start-EXO ignore" -Level 'WARN'
        return
    }

    # --- Interpreteurs Python ----------------------------------------------
    $pythonStt    = Join-Path $script:ProjectDir '.venv_stt_tts\Scripts\python.exe'
    $pythonVenv   = Join-Path $script:ProjectDir '.venv\Scripts\python.exe'
    $pythonOrpheus = Join-Path $script:ProjectDir 'services\orpheus\venv\Scripts\python.exe'

    if (-not (Test-Path $pythonStt))  { Write-Launcher "venv_stt_tts manquant : $pythonStt" -Level 'FAIL' }
    if (-not (Test-Path $pythonVenv)) { Write-Launcher "venv manquant : $pythonVenv"        -Level 'FAIL' }

    # --- Reset du PID store -------------------------------------------------
    Clear-EXOPidStore

    # --- Ports (alignes sur config/services.json + HealthCheck.cpp) ---------
    # TTS : 8767 (production). NB : un environnement de bench peut utiliser
    # 8867, mais le client Qt et les configs pointent sur 8767.
    $TTS_PORT = 8767

    # Engine TTS selectionnable via $env:EXO_TTS_ENGINE :
    #   "cosyvoice" (defaut) -> python/tts/tts_server_streaming.py    (.venv_stt_tts)
    #   "orpheus"            -> services/orpheus/server_ws.py         (services/orpheus/venv)
    # Les deux exposent le MEME protocole WS + /health sur le MEME port.
    $ttsEngine = ($env:EXO_TTS_ENGINE | ForEach-Object { $_.ToLower() })
    if (-not $ttsEngine) { $ttsEngine = 'cosyvoice' }

    if ($ttsEngine -eq 'orpheus') {
        if (-not (Test-Path $pythonOrpheus)) {
            Write-Launcher "venv Orpheus manquant : $pythonOrpheus -- bascule sur cosyvoice" -Level 'WARN'
            $ttsEngine = 'cosyvoice'
        }
    }

    if ($ttsEngine -eq 'orpheus') {
        $ttsPython  = $pythonOrpheus
        $ttsScript  = 'services/orpheus/server_ws.py'
        $ttsTimeout = 60
        Write-Launcher "TTS engine = Orpheus 3B FR (GGUF Q8) CUDA" -Level 'INFO'
    } else {
        $ttsPython  = $pythonStt
        $ttsScript  = 'python/tts/tts_server_streaming.py'
        $ttsTimeout = 10
        Write-Launcher "TTS engine = CosyVoice2 CUDA" -Level 'INFO'
    }

    # =======================================================================
    #  Services CRITIQUES (healthcheck synchrone, ~10 s)
    # =======================================================================
    Write-Launcher "--- Demarrage services critiques ---" -Level 'INFO'

    Start-EXOService -Name 'TTS'           -Python $ttsPython  `
        -Script $ttsScript -Port $TTS_PORT `
        -ExtraArgs @('--host', '0.0.0.0', '--port', $TTS_PORT.ToString()) `
        -HealthTimeoutSeconds $ttsTimeout

    Start-EXOService -Name 'STT'           -Python $pythonStt  `
        -Script 'python/stt/stt_server.py'           -Port 8766 `
        -ExtraArgs @('--backend','whispercpp','--model','small','--beam-size','1','--language','fr','--device','vulkan') `
        -HealthTimeoutSeconds 10

    Start-EXOService -Name 'Orchestrator'  -Python $pythonVenv `
        -Script 'python/orchestrator/exo_server.py'  -Port 8765 `
        -HealthTimeoutSeconds 10

    Start-EXOService -Name 'Memory'        -Python $pythonStt  `
        -Script 'python/memory/memory_server.py'     -Port 8771 `
        -HealthTimeoutSeconds 10

    Start-EXOService -Name 'Context'       -Python $pythonStt  `
        -Script 'python/context/context_engine.py'   -Port 8777 `
        -HealthTimeoutSeconds 10

    Start-EXOService -Name 'Planner'       -Python $pythonStt  `
        -Script 'python/planner/task_planner_server.py' -Port 8778 `
        -HealthTimeoutSeconds 10

    Start-EXOService -Name 'Executor'      -Python $pythonStt  `
        -Script 'python/executor/task_executor_server.py' -Port 8779 `
        -HealthTimeoutSeconds 10

    Start-EXOService -Name 'Verifier'      -Python $pythonStt  `
        -Script 'python/verifier/task_verifier_server.py' -Port 8780 `
        -HealthTimeoutSeconds 10

    Start-EXOService -Name 'System'        -Python $pythonStt  `
        -Script 'python/tools/system_service.py'     -Port 8783 `
        -HealthTimeoutSeconds 10

    # =======================================================================
    #  Services LAZY (lancement en background, pas d'attente bloquante)
    # =======================================================================
    Write-Launcher "--- Demarrage services lazy ---" -Level 'INFO'

    Start-EXOService -Name 'NLU'       -Python $pythonStt  `
        -Script 'python/nlu/nlu_server.py'             -Port 8772 -HealthTimeoutSeconds 0
    Start-EXOService -Name 'VAD'       -Python $pythonStt  `
        -Script 'python/vad/vad_server.py'             -Port 8768 -HealthTimeoutSeconds 0
    Start-EXOService -Name 'Wakeword'  -Python $pythonStt  `
        -Script 'python/wakeword/wakeword_server.py'   -Port 8770 -HealthTimeoutSeconds 0
    Start-EXOService -Name 'Tools'     -Python $pythonVenv `
        -Script 'python/tools/tools_server.py'         -Port 8776 -HealthTimeoutSeconds 0
    Start-EXOService -Name 'Websearch' -Python $pythonVenv `
        -Script 'python/websearch/websearch_server.py' -Port 8773 -HealthTimeoutSeconds 0
    Start-EXOService -Name 'News'      -Python $pythonVenv `
        -Script 'python/news/news_server.py'           -Port 8774 -HealthTimeoutSeconds 0
    Start-EXOService -Name 'Knowledge' -Python $pythonVenv `
        -Script 'python/knowledge/knowledge_server.py' -Port 8775 -HealthTimeoutSeconds 0

    # =======================================================================
    #  GUI EXO (RaspberryAssistant.exe) — Qt affiche sa propre fenetre.
    #  Aucune console PowerShell n'est ouverte ; les flux sont rediriges.
    # =======================================================================
    $exePath = Join-Path $script:ProjectDir 'build\Release\RaspberryAssistant.exe'
    if (-not (Test-Path $exePath)) {
        Write-Launcher "GUI introuvable : $exePath (compilez Release)" -Level 'FAIL'
    } else {
        # Resolution runtime Qt
        $exeDir = Split-Path -Parent $exePath
        $bundledQt = Join-Path $exeDir 'Qt6Core.dll'
        if (-not (Test-Path $bundledQt)) {
            $qtCandidates = @()
            if ($env:QT_BIN_PATH) { $qtCandidates += $env:QT_BIN_PATH }
            $qtCandidates += Get-ChildItem 'C:\Qt' -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName 'msvc2022_64\bin' }
            $qtPath = $qtCandidates |
                Where-Object { $_ -and (Test-Path (Join-Path $_ 'Qt6Core.dll')) } |
                Select-Object -First 1
            if ($qtPath -and ($env:PATH -notlike "*$qtPath*")) {
                $env:PATH = "$qtPath;$env:PATH"
                Write-Launcher "PATH Qt ajoute : $qtPath" -Level 'INFO'
            } elseif (-not $qtPath) {
                Write-Launcher "Runtime Qt introuvable - GUI ne demarrera pas" -Level 'FAIL'
            }
        }

        $guiStdout = Join-Path $script:LogDir 'gui.log'
        $guiStderr = Join-Path $script:LogDir 'gui.err.log'
        try {
            # Note : Qt affiche sa propre fenetre applicative (legitime).
            # WindowStyle Hidden masque uniquement la console, pas le GUI Qt.
            $guiProc = Start-Process -FilePath $exePath `
                -WorkingDirectory $exeDir `
                -PassThru `
                -RedirectStandardOutput $guiStdout `
                -RedirectStandardError  $guiStderr
            Save-EXOPidEntry -Name 'GUI' -ProcessId $guiProc.Id -Port 0
            Write-Launcher "GUI lance (PID $($guiProc.Id))" -Level 'OK'
        } catch {
            Write-Launcher "GUI : echec ($($_.Exception.Message))" -Level 'FAIL'
        }
    }

    Write-Launcher "================ Start-EXO termine ================" -Level 'OK'
}

# ===========================================================================
#  Stop-EXO
# ===========================================================================
function Stop-EXO {
    [CmdletBinding()]
    param()

    Write-Launcher "================ Stop-EXO ================" -Level 'INFO'

    $store = Get-EXOPidStore
    foreach ($name in $store.Keys) {
        $entry = $store[$name]
        $procId = [int]$entry.pid
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Launcher "$name (PID $procId) tue" -Level 'OK'
        } catch {
            Write-Launcher "$name (PID $procId) deja arrete" -Level 'INFO'
        }
    }

    # Filet de securite : tuer aussi tout RaspberryAssistant.exe orphelin.
    Get-Process -Name 'RaspberryAssistant' -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
            Write-Launcher "RaspberryAssistant orphelin PID $($_.Id) tue" -Level 'OK'
        } catch {
            Write-Launcher "RaspberryAssistant PID $($_.Id) : $($_.Exception.Message)" -Level 'WARN'
        }
    }

    Clear-EXOPidStore
    Write-Launcher "================ Stop-EXO termine ================" -Level 'OK'
}

# ===========================================================================
#  Restart-EXO
# ===========================================================================
function Restart-EXO {
    [CmdletBinding()]
    param()
    Write-Launcher "================ Restart-EXO ================" -Level 'INFO'
    Stop-EXO
    Start-Sleep -Seconds 2
    Start-EXO
}

# ===========================================================================
#  Get-EXOStatus
# ===========================================================================
function Get-EXOStatus {
    [CmdletBinding()]
    param()
    $store = Get-EXOPidStore
    if (-not $store -or $store.Count -eq 0) {
        Write-Output 'Aucun service EXO enregistre.'
        return
    }
    $rows = foreach ($name in ($store.Keys | Sort-Object)) {
        $e = $store[$name]
        $alive = $false
        try { $alive = [bool](Get-Process -Id ([int]$e.pid) -ErrorAction Stop) } catch {}
        $listen = if ($e.port -gt 0) { Test-PortListening -Port ([int]$e.port) } else { $null }
        [pscustomobject]@{
            Service   = $name
            PID       = $e.pid
            Port      = $e.port
            Alive     = $alive
            Listening = $listen
        }
    }
    $rows | Format-Table -AutoSize
}

# ===========================================================================
#  Auto-execution si invoque directement (raccourci / double-clic)
# ===========================================================================
# Si le script est dot-source (`. .\launch_exo_silent.ps1`),
# $MyInvocation.InvocationName vaut '.', on n'execute alors que les definitions.
if ($MyInvocation.InvocationName -ne '.') {
    Start-EXO
}
