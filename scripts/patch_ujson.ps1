$files = @(
  'python\context\context_engine.py',
  'python\executor\task_executor_server.py',
  'python\knowledge\knowledge_server.py',
  'python\memory\memory_server.py',
  'python\news\news_server.py',
  'python\nlu\nlu_server.py',
  'python\planner\task_planner_server.py',
  'python\verifier\task_verifier_server.py',
  'python\websearch\websearch_server.py',
  'python\wakeword\wakeword_server.py',
  'python\tts\tts_server.py',
  'python\stt\stt_server.py',
  'python\vad\vad_server.py',
  'python\tools\tools_server.py',
  'python\tools\system_service.py',
  'python\orchestrator\exo_server.py'
)
$replacement = "try:`r`n    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)`r`nexcept ImportError:`r`n    import json"
$count = 0
foreach ($f in $files) {
  $p = Join-Path 'D:\EXO' $f
  if (-not (Test-Path $p)) { Write-Host "SKIP missing: $f"; continue }
  $content = Get-Content $p -Raw -Encoding UTF8
  if ($content -match 'import ujson as json') { Write-Host "SKIP already patched: $f"; continue }
  $rx = New-Object System.Text.RegularExpressions.Regex('^import json\r?$', [System.Text.RegularExpressions.RegexOptions]::Multiline)
  if ($rx.Matches($content).Count -eq 0) { Write-Host "SKIP no plain import: $f"; continue }
  $new = $rx.Replace($content, $replacement, 1)
  Set-Content -Path $p -Value $new -Encoding UTF8 -NoNewline
  $count++
  Write-Host "PATCHED: $f"
}
Write-Host "--- Total patched: $count ---"
