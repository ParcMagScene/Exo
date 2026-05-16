param([string]$Csv)
$rows = Get-Content $Csv | Select-Object -Skip 3 | Where-Object { $_ -notmatch 'DEAD' -and $_ -ne '' }
$data = $rows | ForEach-Object {
    $f = $_ -split ','
    [pscustomobject]@{ ts=$f[0]; svc=$f[1]; cpu=[double]$f[3]; ram=[double]$f[4]; thr=[int]$f[5] }
}
"{0,-15} {1,8} {2,8} {3,8} {4,9} {5,9} {6,8}" -f 'Service','cpu_avg','cpu_p95','cpu_max','ram_avg','ram_max','thr_avg'
"{0,-15} {1,8} {2,8} {3,8} {4,9} {5,9} {6,8}" -f '-------','-------','-------','-------','-------','-------','-------'
$groups = $data | Group-Object svc
$enriched = foreach ($g in $groups) {
    $cpus = $g.Group.cpu | Sort-Object
    $cpuStats = $cpus | Measure-Object -Average -Maximum
    $ramStats = $g.Group.ram | Measure-Object -Average -Maximum
    $thrStats = $g.Group.thr | Measure-Object -Average
    [pscustomobject]@{
        Service = $g.Name
        cpu_avg = [math]::Round($cpuStats.Average, 1)
        cpu_p95 = [math]::Round($cpus[[int]($cpus.Count * 0.95)], 1)
        cpu_max = [math]::Round($cpuStats.Maximum, 1)
        ram_avg = [math]::Round($ramStats.Average, 0)
        ram_max = [math]::Round($ramStats.Maximum, 0)
        thr_avg = [math]::Round($thrStats.Average, 0)
    }
}
$enriched | Sort-Object cpu_avg -Descending | ForEach-Object {
    "{0,-15} {1,8} {2,8} {3,8} {4,9} {5,9} {6,8}" -f $_.Service, $_.cpu_avg, $_.cpu_p95, $_.cpu_max, $_.ram_avg, $_.ram_max, $_.thr_avg
}
