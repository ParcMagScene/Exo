# Aggregation post-profile
param([string]$Path)
if (-not $Path) {
    $Path = (Get-ChildItem D:\EXO\logs\profile_*.csv | Where-Object {$_.Name -notmatch 'profile_gpu'} | Sort LastWriteTime -Desc | Select -First 1).FullName
}
$gpuPath = $Path -replace 'profile_(?!gpu)', 'profile_gpu_'
"=== Source: $Path ==="

$rows = Import-Csv $Path -Header timestamp,service,pid,cpu_pct,ram_mb,threads,handles |
    Where-Object { $_.timestamp -and $_.timestamp -notmatch '^#' -and $_.timestamp -ne 'timestamp' -and $_.cpu_pct -ne 'DEAD' }

$ticks = ($rows | Group-Object timestamp).Count
"Ticks: $ticks"
"Services: $((($rows | Select -Expand service -Unique) -join ', '))"
""
"=== A. CPU & RAM par service (avg / p95 / max / RAM end - RAM start) ==="

$by = $rows | Group-Object service | Sort Name
$tbl = foreach ($g in $by) {
    $cpu = $g.Group | ForEach-Object { [double]$_.cpu_pct } | Sort-Object
    $ram = $g.Group | ForEach-Object { [double]$_.ram_mb }
    $thr = $g.Group | ForEach-Object { [int]$_.threads }
    $n = $cpu.Count
    if ($n -eq 0) { continue }
    $avg = [math]::Round(($cpu | Measure-Object -Average).Average, 2)
    $p95 = [math]::Round($cpu[[math]::Min($n-1,[int]($n*0.95))], 2)
    $mx  = [math]::Round(($cpu | Measure-Object -Maximum).Maximum, 2)
    $ramAvg = [math]::Round(($ram | Measure-Object -Average).Average, 1)
    $ramMax = [math]::Round(($ram | Measure-Object -Maximum).Maximum, 1)
    $ramStart = [math]::Round($ram[0],1)
    $ramEnd = [math]::Round($ram[-1],1)
    $ramDelta = [math]::Round($ramEnd - $ramStart, 1)
    $thrMax = ($thr | Measure-Object -Maximum).Maximum
    [pscustomobject]@{
        Service=$g.Name
        CPU_avg=$avg; CPU_p95=$p95; CPU_max=$mx
        RAM_avg=$ramAvg; RAM_max=$ramMax
        RAM_start=$ramStart; RAM_end=$ramEnd; RAM_delta=$ramDelta
        Thr_max=$thrMax
    }
}
$tbl | Sort-Object CPU_avg -Descending | Format-Table -AutoSize | Out-String -Width 200

# GPU section
if (Test-Path $gpuPath) {
    "`n=== B. GPU global (samples ~2s) ==="
    $g = Import-Csv $gpuPath -Header timestamp,gpu_util_pct,vram_used_mb,vram_free_mb |
        Where-Object { $_.timestamp -and $_.timestamp -notmatch '^#' -and $_.timestamp -ne 'timestamp' }
    $util = $g | ForEach-Object { [int]$_.gpu_util_pct } | Sort-Object
    $vram = $g | ForEach-Object { [int]$_.vram_used_mb }
    $n = $util.Count
    "GPU samples: $n"
    "GPU util  : avg=$([math]::Round(($util|Measure-Object -Average).Average,1))% p95=$($util[[math]::Min($n-1,[int]($n*0.95))])% max=$(($util|Measure-Object -Maximum).Maximum)%"
    "VRAM used : avg=$([math]::Round(($vram|Measure-Object -Average).Average,0)) MB max=$(($vram|Measure-Object -Maximum).Maximum) MB delta=$([math]::Round($vram[-1]-$vram[0],0)) MB"
}

# Top RAM growth
"`n=== C. Top 5 fuites memoire potentielles (delta RAM positif > 5 MB) ==="
$tbl | Where-Object { $_.RAM_delta -gt 5 } | Sort-Object RAM_delta -Desc | Select -First 5 | Format-Table -AutoSize | Out-String -Width 200

# Top CPU
"`n=== D. Top 5 consommateurs CPU (avg) ==="
$tbl | Sort-Object CPU_avg -Desc | Select -First 5 | Format-Table -AutoSize | Out-String -Width 200
