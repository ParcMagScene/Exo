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
#    powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "D:\EXO\launch_exo_silent.ps1"
#  Demarrer dans :
#    D:\EXO
#  Executer en :
#    Reduit (le -WindowStyle Hidden masque deja la fenetre).
#
#  COMMANDES DISPONIBLES (en interactif)
#  -------------------------------------
#    . D:\EXO\launch_exo_silent.ps1   # dot-source pour exposer les fonctions
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
$script:ProjectDir = 'D:/EXO'
$script:SsdRoot    = 'D:/EXO'

# --- Forcer le working directory à D:/EXO/ ---
if (((Get-Location).Path -replace '\\','/') -ne 'D:/EXO') {
    Write-Host "ERREUR : Ce lanceur doit être exécuté depuis D:/EXO/." -ForegroundColor Red
    Set-Location "D:/EXO/"
    if (((Get-Location).Path -replace '\\','/') -ne 'D:/EXO') {
        Write-Host "Impossible de corriger le working directory. Arrêt." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Working directory corrigé en D:/EXO/." -ForegroundColor Yellow
    }
}
$script:LogDir     = Join-Path $script:ProjectDir 'logs'
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
#
#  Sur Windows, les venv utilisent une SHIM `.venv\Scripts\python.exe` qui
#  spawn ensuite le vrai `Python311\python.exe` (worker). On stocke les DEUX
#  PIDs (shim + worker) pour garantir un Stop-EXO complet sans orphelins.
# ----------------------------------------------------------------------------
function Get-WorkerPidForShim {
    <# Resout le PID du worker Python (child) a partir du PID de la shim venv.
       Strategies (avec retry court pour tolerer la race au demarrage) :
         1. Si Port>0 et listening -> OwningProcess du port (le plus fiable).
         2. Sinon : Win32_Process avec ParentProcessId == ShimPid (1ere occurrence).
       Retry jusqu'a TimeoutMs (defaut 2000ms) puis retourne 0.
    #>
    param([int]$ShimPid, [int]$Port = 0, [int]$TimeoutMs = 2000)
    $deadline = (Get-Date).AddMilliseconds($TimeoutMs)
    while ((Get-Date) -lt $deadline) {
        if ($Port -gt 0) {
            $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($conn -and $conn.OwningProcess -gt 0) { return [int]$conn.OwningProcess }
        }
        try {
            $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ShimPid" -ErrorAction Stop | Select-Object -First 1
            if ($child) { return [int]$child.ProcessId }
        } catch {}
        Start-Sleep -Milliseconds 150
    }
    return 0
}

function Save-EXOPidEntry {
    param(
        [string]$Name,
        [int]$ProcessId,
        [int]$Port,
        [int]$WorkerProcessId = 0
    )
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
        pid        = $ProcessId
        worker_pid = $WorkerProcessId
        port       = $Port
        started    = (Get-Date -Format 'o')
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
            # Resout le PID du worker child (vrai Python qui ecoute le port).
            $workerPid = Get-WorkerPidForShim -ShimPid $proc.Id -Port $Port -TimeoutMs 5000
            if ($workerPid -gt 0 -and $workerPid -ne $proc.Id) {
                Save-EXOPidEntry -Name $Name -ProcessId $proc.Id -Port $Port -WorkerProcessId $workerPid
                Write-Launcher "$Name ready (shim=$($proc.Id), worker=$workerPid)" -Level 'OK'
            } else {
                Write-Launcher "$Name ready (worker_pid non resolu - fallback parent-PID actif)" -Level 'OK'
            }
        } else {
            Write-Launcher "$Name timeout (port $Port pas pret en ${HealthTimeoutSeconds}s)" -Level 'FAIL'
        }
    }
}

# --- Orphan cleanup --------------------------------------------------------
function Remove-EXOOrphanWorkers {
    <# Detecte et tue les python.exe qui executent un script EXO mais
       n'ecoutent aucun port EXO et ne sont pas referencees dans
       exo_pids.json (orphelins de boots precedents ou de double-spawn).
       Ne touche jamais a Orpheus (services\orpheus\).
    #>
    $exoPorts = @(8765,8766,8767,8768,8770,8771,8772,8773,8774,8775,8776,8777,8778,8779,8780,8783,8784,8785,8790)
    $listeners = @{}
    foreach ($p in $exoPorts) {
        $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($c) { $listeners[[int]$c.OwningProcess] = $p }
    }
    # Set de PIDs legitimes (shims + workers connus) issus du store.
    $known = @{}
    try {
        if (Test-Path $script:PidStore) {
            $store = Get-Content $script:PidStore -Raw | ConvertFrom-Json
            foreach ($prop in $store.PSObject.Properties) {
                $e = $prop.Value
                if ($e.pid)        { $known[[int]$e.pid] = $true }
                if ($e.worker_pid) { $known[[int]$e.worker_pid] = $true }
            }
        }
    } catch {}
    $killed = 0; $freedMb = 0
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
    foreach ($pr in $procs) {
        $cmd = if ($pr.CommandLine) { $pr.CommandLine } else { '' }
        # On ne cible que les workers EXO (chargent un script EXO connu).
        if ($cmd -notmatch 'D:[\\/]EXO[\\/](python|services)[\\/]') { continue }
        # Jamais Orpheus.
        if ($cmd -match 'services[\\/]orpheus[\\/]') { continue }
        # On preserve les listeners actifs.
        if ($listeners.ContainsKey([int]$pr.ProcessId)) { continue }
        # On preserve tout PID present dans exo_pids.json (shim ou worker connu).
        if ($known.ContainsKey([int]$pr.ProcessId)) { continue }
        # On preserve aussi tout child d'un shim connu (le worker_pid n'a
        # peut-etre pas encore ete capture au moment du cleanup).
        if ($known.ContainsKey([int]$pr.ParentProcessId)) { continue }
        # Reste : workers EXO inconnus ET sans port = orphelins surs.
        try {
            $ramMb = [math]::Round($pr.WorkingSetSize/1MB,0)
            Stop-Process -Id $pr.ProcessId -Force -ErrorAction Stop
            Write-Launcher "Orphan worker tue : PID=$($pr.ProcessId) RAM=${ramMb}MB cmd=$($cmd.Substring(0,[math]::Min(80,$cmd.Length)))" -Level 'OK'
            $killed++; $freedMb += $ramMb
        } catch {
            Write-Launcher "Orphan PID=$($pr.ProcessId) : echec kill ($($_.Exception.Message))" -Level 'WARN'
        }
    }
    if ($killed -gt 0) {
        Write-Launcher "Orphan cleanup : $killed process(es) tue(s), ~${freedMb}MB libere(s)" -Level 'OK'
    } else {
        Write-Launcher "Orphan cleanup : aucun orphelin detecte" -Level 'INFO'
    }
    return $killed
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

    # --- Génération du timestamp de session EXO ----------------------------
    if (-not $env:EXO_SESSION_TIMESTAMP) {
        $env:EXO_SESSION_TIMESTAMP = (Get-Date -Format 'yyyyMMdd_HHmmss')
        Write-Launcher "EXO_SESSION_TIMESTAMP généré : $env:EXO_SESSION_TIMESTAMP" -Level 'INFO'
    } else {
        Write-Launcher "EXO_SESSION_TIMESTAMP déjà présent : $env:EXO_SESSION_TIMESTAMP" -Level 'INFO'
    }

    # --- Variables d'environnement EXO --------------------------------------
    $env:PYTHONPATH            = Join-Path $script:ProjectDir 'python'
    $env:EXO_SSD_ROOT          = $script:SsdRoot
    $env:EXO_WHISPER_MODELS    = Join-Path $script:SsdRoot 'models/whisper'
    $env:EXO_WHISPERCPP_BIN    = Join-Path $script:SsdRoot 'whispercpp/build_vk/bin/Release'
    $env:EXO_ORPHEUS_MODELS    = Join-Path $script:SsdRoot 'models/orpheus_fr_gguf'
    $env:EXO_FAISS_DIR         = Join-Path $script:SsdRoot 'faiss/semantic_memory'
    $env:EXO_WAKEWORD_MODELS   = Join-Path $script:SsdRoot 'models/wakeword'
    $env:EXO_FILES_DIR         = Join-Path $script:SsdRoot 'files'
    $env:EXO_LOGS_DIR          = $script:LogDir
    $env:HF_HOME               = Join-Path $script:SsdRoot 'cache/huggingface'
    $env:TRANSFORMERS_CACHE    = Join-Path $script:SsdRoot 'cache/huggingface/hub'
    $env:TORCH_HOME            = Join-Path $script:SsdRoot 'cache/torch'

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

    # Engine TTS : Orpheus 3B FR (GGUF Q8) CUDA - SEUL moteur supporte.
    # (politique 2026-05-03 : pipeline TTS unique = Orpheus 3B FR GGUF Q8)
    if (-not (Test-Path $pythonOrpheus)) {
        Write-Launcher "venv Orpheus manquant : $pythonOrpheus - TTS indisponible" -Level 'FAIL'
        return
    }
    $ttsPython  = $pythonOrpheus
    $ttsScript  = 'services/orpheus/server_ws.py'
    $ttsTimeout = 60
    # Anti-craquements : chunk WS = 40 ms PCM16 mono @24 kHz = 960 samples = 1920 B.
    # Le serveur pace l'envoi sur la duree reelle (40 ms par chunk) -> debit
    # constant cote client, pas de burst, pas d'underflow du ring buffer.
    if (-not $env:ORPHEUS_WS_CHUNK_BYTES) { $env:ORPHEUS_WS_CHUNK_BYTES = '1920' }
    Write-Launcher "TTS engine = Orpheus 3B FR (GGUF Q8) CUDA (chunk=$env:ORPHEUS_WS_CHUNK_BYTES B)" -Level 'INFO'

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

    # --- Auto-cleanup orphelins (zombies de boots precedents ou double-spawn).
    try { Remove-EXOOrphanWorkers | Out-Null } catch {
        Write-Launcher "Remove-EXOOrphanWorkers : $($_.Exception.Message)" -Level 'WARN'
    }

    Write-Launcher "================ Start-EXO termine ================" -Level 'OK'
}

# ===========================================================================
#  Stop-EXO
# ===========================================================================
function Stop-EXO {
    [CmdletBinding()]
    param(
        [int]$GuiGraceMs = 3000
    )

    Write-Launcher "================ Stop-EXO ================" -Level 'INFO'

    # 1) Phase gracieuse : envoyer CloseMainWindow a la GUI Qt -> aboutToQuit
    #    -> ServiceSupervisor::shutdownAll() (ferme les QProcess enfants
    #    et destructeurs TTSManager / VoicePipeline).
    $guiProcs = Get-Process -Name 'RaspberryAssistant' -ErrorAction SilentlyContinue
    foreach ($g in $guiProcs) {
        try {
            $closed = $g.CloseMainWindow()
            if ($closed) {
                Write-Launcher "GUI PID $($g.Id) : CloseMainWindow envoye" -Level 'OK'
            } else {
                Write-Launcher "GUI PID $($g.Id) : pas de fenetre principale" -Level 'WARN'
            }
        } catch {
            Write-Launcher "GUI PID $($g.Id) : CloseMainWindow echec ($($_.Exception.Message))" -Level 'WARN'
        }
    }

    if ($guiProcs.Count -gt 0 -and $GuiGraceMs -gt 0) {
        $deadline = (Get-Date).AddMilliseconds($GuiGraceMs)
        while ((Get-Date) -lt $deadline) {
            $alive = Get-Process -Name 'RaspberryAssistant' -ErrorAction SilentlyContinue
            if (-not $alive) { break }
            Start-Sleep -Milliseconds 100
        }
    }

    # 2) Phase force : tuer tous les services Python par PID stocke.
    #    On tue D'ABORD le worker child puis la shim parent (ordre important :
    #    si on tue la shim en premier, le child devient orphelin sous Windows).
    $store = Get-EXOPidStore
    foreach ($name in $store.Keys) {
        $entry = $store[$name]
        $shimPid   = [int]$entry.pid
        $workerPid = if ($entry.PSObject.Properties.Name -contains 'worker_pid') { [int]$entry.worker_pid } else { 0 }
        # Worker d'abord
        if ($workerPid -gt 0 -and $workerPid -ne $shimPid) {
            try {
                Stop-Process -Id $workerPid -Force -ErrorAction Stop
                Write-Launcher "$name worker (PID $workerPid) tue" -Level 'OK'
            } catch {
                Write-Launcher "$name worker (PID $workerPid) deja arrete" -Level 'INFO'
            }
        }
        # Puis la shim
        try {
            Stop-Process -Id $shimPid -Force -ErrorAction Stop
            Write-Launcher "$name shim (PID $shimPid) tue" -Level 'OK'
        } catch {
            Write-Launcher "$name shim (PID $shimPid) deja arrete" -Level 'INFO'
        }
    }

    # 3) Filet de securite : tuer tout RaspberryAssistant.exe encore vivant.
    Get-Process -Name 'RaspberryAssistant' -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction Stop
            Write-Launcher "RaspberryAssistant orphelin PID $($_.Id) tue" -Level 'OK'
        } catch {
            Write-Launcher "RaspberryAssistant PID $($_.Id) : $($_.Exception.Message)" -Level 'WARN'
        }
    }

    # 4) Filet ULTIME : balayer tous les ports EXO et tuer le owner restant.
    #    Couvre les workers dont le PID n'a jamais ete capture dans le store.
    $exoPorts = @(8765,8766,8767,8768,8770,8771,8772,8773,8774,8775,8776,8777,8778,8779,8780,8783,8784,8785,8790)
    foreach ($p in $exoPorts) {
        $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($c -and $c.OwningProcess -gt 0) {
            try {
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
                Write-Launcher "Port $p : owner PID $($c.OwningProcess) tue (orphelin)" -Level 'OK'
            } catch {}
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
