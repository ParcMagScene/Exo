# EXO Runtime Profiler
# Sample CPU%, RAM_MB, threads par service + GPU util/VRAM toutes les ~500 ms.
# Sortie : D:\EXO\logs\profile_<ts>.csv
param(
    [int]$DurationSec = 180,
    [int]$IntervalMs  = 500
)

$ErrorActionPreference = 'Continue'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$out = "D:\EXO\logs\profile_$ts.csv"
$gpuOut = "D:\EXO\logs\profile_gpu_$ts.csv"

# Build mapping service -> real PID (worker_pid prefere, sinon listener du port, sinon shim pid)
$store = Get-Content D:\EXO\logs\exo_pids.json -Raw | ConvertFrom-Json
$svc = @{}
foreach ($p in $store.PSObject.Properties) {
    $name = $p.Name; $entry = $p.Value
    $pidUse = 0
    if ($entry.worker_pid -and $entry.worker_pid -gt 0) { $pidUse = [int]$entry.worker_pid }
    elseif ($entry.port -and $entry.port -gt 0) {
        $c = Get-NetTCPConnection -LocalPort $entry.port -State Listen -EA SilentlyContinue | Select -First 1
        if ($c) { $pidUse = [int]$c.OwningProcess }
    }
    if ($pidUse -eq 0 -and $entry.pid -gt 0) { $pidUse = [int]$entry.pid }
    if ($pidUse -gt 0) { $svc[$name] = $pidUse }
}

# Add Orpheus (any python.exe in services\orpheus venv)
$orph = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -EA SilentlyContinue | Where-Object { $_.CommandLine -match 'services\\orpheus' } | Select -First 1
if ($orph) { $svc['Orpheus'] = [int]$orph.ProcessId }

# Add RaspberryAssistant.exe (GUI C++)
$gui = Get-Process RaspberryAssistant -EA SilentlyContinue | Select -First 1
if ($gui) { $svc['GUI_cpp'] = $gui.Id }

# Add whisper-server.exe
$wsv = Get-Process whisper-server -EA SilentlyContinue | Select -First 1
if ($wsv) { $svc['WhisperSrv'] = $wsv.Id }

"# Profiler start $ts duration=${DurationSec}s interval=${IntervalMs}ms" | Out-File $out
"# Services: $($svc.Keys -join ', ')" | Add-Content $out
"timestamp,service,pid,cpu_pct,ram_mb,threads,handles" | Add-Content $out
"timestamp,gpu_util_pct,vram_used_mb,vram_free_mb" | Out-File $gpuOut

# Get CPU baseline (TotalProcessorTime delta method)
$prev = @{}
$nproc = [Environment]::ProcessorCount
foreach ($n in $svc.Keys) {
    $p = Get-Process -Id $svc[$n] -EA SilentlyContinue
    if ($p) { $prev[$n] = @{ cpu = $p.TotalProcessorTime.TotalMilliseconds; ts = (Get-Date) } }
}
Start-Sleep -Milliseconds 200

$end = (Get-Date).AddSeconds($DurationSec)
$tick = 0
while ((Get-Date) -lt $end) {
    $now = Get-Date
    $nowIso = $now.ToString('o')

    # GPU sample (every 4 ticks ~= 2s pour limiter surcout nvidia-smi)
    if ($tick % 4 -eq 0) {
        try {
            $g = (& nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.free --format=csv,noheader,nounits) -split ','
            if ($g.Count -ge 3) { "$nowIso,$($g[0].Trim()),$($g[1].Trim()),$($g[2].Trim())" | Add-Content $gpuOut }
        } catch {}
    }

    foreach ($n in @($svc.Keys)) {
        $pid_ = $svc[$n]
        $p = Get-Process -Id $pid_ -EA SilentlyContinue
        if (-not $p) { "$nowIso,$n,$pid_,DEAD,0,0,0" | Add-Content $out; continue }
        $curCpu = $p.TotalProcessorTime.TotalMilliseconds
        $curTs  = $now
        if ($prev.ContainsKey($n)) {
            $dt = ($curTs - $prev[$n].ts).TotalMilliseconds
            if ($dt -gt 0) {
                $cpuPct = [math]::Round((($curCpu - $prev[$n].cpu) / $dt) * 100 / $nproc, 2)
            } else { $cpuPct = 0 }
        } else { $cpuPct = 0 }
        $prev[$n] = @{ cpu = $curCpu; ts = $curTs }
        $ram = [math]::Round($p.WorkingSet64 / 1MB, 1)
        $thr = $p.Threads.Count
        $hdl = $p.HandleCount
        "$nowIso,$n,$pid_,$cpuPct,$ram,$thr,$hdl" | Add-Content $out
    }

    $tick++
    $sleep = $IntervalMs - ((Get-Date) - $now).TotalMilliseconds
    if ($sleep -gt 10) { Start-Sleep -Milliseconds ([int]$sleep) }
}

"# done at $(Get-Date -Format 'o') ticks=$tick" | Add-Content $out
Write-Host "PROFILE_DONE $out"
