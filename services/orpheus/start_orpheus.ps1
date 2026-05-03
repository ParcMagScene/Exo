# =============================================================================
#  start_orpheus.ps1 - Lance le serveur Orpheus FR (silencieux, CUDA)
#
#  Usage :
#    . D:\EXO\project\services\orpheus\start_orpheus.ps1
#    Start-Orpheus
#    Stop-Orpheus
#    Get-OrpheusStatus
# =============================================================================

$ErrorActionPreference = 'Stop'

$script:OrpheusDir   = 'D:\EXO\project\services\orpheus'
$script:OrpheusVenv  = Join-Path $script:OrpheusDir 'venv'
$script:OrpheusPy    = Join-Path $script:OrpheusVenv 'Scripts\python.exe'
$script:OrpheusLog   = 'D:\EXO\logs\orpheus_server.log'
$script:OrpheusErr   = 'D:\EXO\logs\orpheus_server.err.log'
$script:OrpheusPort  = 8899
$script:OrpheusModel = 'D:\EXO\models\orpheus_fr_gguf\Orpheus-3b-French-FT-Q8_0.gguf'
$script:OrpheusPidF  = Join-Path $script:OrpheusDir '.orpheus.pid'

function Test-OrpheusPort {
    try {
        $tcp = Get-NetTCPConnection -LocalPort $script:OrpheusPort -State Listen -ErrorAction Stop
        return ($tcp -ne $null)
    } catch { return $false }
}

function Start-Orpheus {
    [CmdletBinding()] param()

    if (-not (Test-Path $script:OrpheusPy)) {
        Write-Host "[Orpheus] venv introuvable : $script:OrpheusPy" -ForegroundColor Red
        Write-Host "[Orpheus] Lancer d'abord les etapes d'installation (cf. README)." -ForegroundColor Red
        return
    }
    if (-not (Test-Path $script:OrpheusModel)) {
        Write-Host "[Orpheus] GGUF introuvable : $script:OrpheusModel" -ForegroundColor Red
        Write-Host "[Orpheus] Telecharger via : huggingface-cli download lex-au/Orpheus-3b-French-FT-Q8_0.gguf" -ForegroundColor Yellow
        return
    }
    if (Test-OrpheusPort) {
        Write-Host "[Orpheus] deja actif sur le port $script:OrpheusPort - skip" -ForegroundColor Yellow
        return
    }

    $logDir = Split-Path -Parent $script:OrpheusLog
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    foreach ($f in @($script:OrpheusLog, $script:OrpheusErr)) {
        if (Test-Path $f) { try { Clear-Content $f -ErrorAction Stop } catch {} }
    }

    $env:ORPHEUS_GGUF_PATH = $script:OrpheusModel
    $env:ORPHEUS_HOST      = '0.0.0.0'
    $env:ORPHEUS_PORT      = $script:OrpheusPort.ToString()
    # Anti-fragmentation memoire CUDA
    $env:PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'

    $args = @(
        '-m','uvicorn','server_gguf:app',
        '--host','0.0.0.0',
        '--port', $script:OrpheusPort.ToString(),
        '--log-level','info'
    )

    $proc = Start-Process -FilePath $script:OrpheusPy `
        -ArgumentList $args `
        -WorkingDirectory $script:OrpheusDir `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $script:OrpheusLog `
        -RedirectStandardError  $script:OrpheusErr

    Set-Content -Path $script:OrpheusPidF -Value $proc.Id -Encoding ASCII
    Write-Host "[Orpheus] lance (PID $($proc.Id), port $script:OrpheusPort)" -ForegroundColor Green
    Write-Host "[Orpheus] logs : $script:OrpheusLog"

    # Attente readiness (jusqu'a 120 s : chargement modele + SNAC)
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 750
        if (Test-OrpheusPort) {
            Write-Host "[Orpheus] ready" -ForegroundColor Green
            return
        }
        if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) {
            Write-Host "[Orpheus] processus mort - voir $script:OrpheusErr" -ForegroundColor Red
            return
        }
    }
    Write-Host "[Orpheus] timeout (120 s) - le modele est peut-etre encore en chargement" -ForegroundColor Yellow
}

function Stop-Orpheus {
    [CmdletBinding()] param()
    if (Test-Path $script:OrpheusPidF) {
        $procPid = Get-Content $script:OrpheusPidF -ErrorAction SilentlyContinue
        if ($procPid) {
            Get-Process -Id $procPid -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $script:OrpheusPidF -ErrorAction SilentlyContinue
    }
    # Filet de securite : tue tout uvicorn restant sur le port 8899
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*uvicorn*server_gguf:app*8899*' -or $_.CommandLine -like '*uvicorn*server:app*8899*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "[Orpheus] stoppe" -ForegroundColor Cyan
}

function Get-OrpheusStatus {
    [CmdletBinding()] param()
    $listening = Test-OrpheusPort
    $pidVal = $null
    if (Test-Path $script:OrpheusPidF) { $pidVal = Get-Content $script:OrpheusPidF }
    $alive = $false
    if ($pidVal) { $alive = [bool](Get-Process -Id $pidVal -ErrorAction SilentlyContinue) }

    [PSCustomObject]@{
        PID       = $pidVal
        Alive     = $alive
        Listening = $listening
        Port      = $script:OrpheusPort
        ModelDir  = $script:OrpheusModel
        LogFile   = $script:OrpheusLog
    }
}

# Si invoque directement (double-clic / -File), on demarre
if ($MyInvocation.InvocationName -ne '.') {
    Start-Orpheus
}
