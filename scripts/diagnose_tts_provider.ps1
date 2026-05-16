param(
    [string[]]$PythonCandidates = @(
        "D:\EXO\.venv\Scripts\python.exe",
        "D:\EXO\.venv_stt_tts\Scripts\python.exe"
    ),
    [string[]]$LogCandidates = @(
        "D:\EXO\logs\tts_stderr.log",
        "D:\EXO\logs\tts_stderr.txt",
        "D:\EXO\logs\tts_server_stderr.log",
        "D:\EXO\logs\tts_server.jsonl",
        "D:\EXO\logs\exo_live_stdout.log",
        "D:\EXO\logs\exo_live_stderr.log"
    )
)

$ErrorActionPreference = "Continue"

Write-Host "=== EXO TTS Provider Diagnostic ==="
Write-Host ""

foreach ($py in $PythonCandidates) {
    if (-not (Test-Path $py)) {
        continue
    }

    Write-Host "--- Python: $py ---"
    & $py -c "import sys, importlib.util; print('exe=',sys.executable); print('python=',sys.version.split()[0]); spec=importlib.util.find_spec('onnxruntime'); print('onnxruntime_installed=',bool(spec));
if spec:
 import onnxruntime as ort
 print('ort_version=',ort.__version__)
 print('providers=',ort.get_available_providers())"

    & $py -m pip list | Select-String -Pattern 'onnxruntime|onnxruntime-gpu|onnxruntime-directml|onnx' -CaseSensitive:$false
    Write-Host ""
}

$patterns = @(
    'CUDAExecutionProvider',
    'DmlExecutionProvider',
    'TensorrtExecutionProvider',
    'onnxruntime',
    'provider',
    'fallback',
    'warning',
    'error'
)

foreach ($log in $LogCandidates) {
    if (-not (Test-Path $log)) {
        continue
    }

    Write-Host "--- Log scan: $log ---"
    $hits = Select-String -Path $log -Pattern $patterns -SimpleMatch -CaseSensitive:$false
    if ($hits) {
        $hits | ForEach-Object { "[{0}] {1}" -f $_.LineNumber, $_.Line }
    } else {
        Write-Host "(no provider/cuda/trt hits)"
    }
    Write-Host ""
}

Write-Host "=== Done ==="
