# Quick setup & test Fish-Speech + E2E Pipeline (Windows)
# Usage: powershell -ExecutionPolicy Bypass -File examples/setup_and_test.ps1

Write-Host "🚀 Assistant E2E Pipeline - Setup & Test" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# 1. Check if Docker is available
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker not found. Install Docker Desktop first:" -ForegroundColor Red
    Write-Host "   https://www.docker.com/products/docker-desktop" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Docker found" -ForegroundColor Green

# 2. Start Fish-Speech if not running
Write-Host ""
Write-Host "🐟 Checking Fish-Speech..." -ForegroundColor Cyan

$fishSpeechRunning = docker ps | Select-String "fish-speech" -ErrorAction SilentlyContinue

if ($fishSpeechRunning) {
    Write-Host "✅ Fish-Speech container already running" -ForegroundColor Green
} else {
    Write-Host "⏳ Starting Fish-Speech container..." -ForegroundColor Yellow
    
    # Pull latest image
    Write-Host "   Pulling latest image..." -ForegroundColor Yellow
    docker pull fish-audio/fish-speech:latest
    
    # Run container
    Write-Host "   Starting container..." -ForegroundColor Yellow
    docker run -d `
      --name fish-speech `
      -p 8000:8000 `
      -v fish-speech-models:/app/models `
      --restart unless-stopped `
      fish-audio/fish-speech:latest 2>&1 | Out-Null
    
    Write-Host "⏳ Waiting for Fish-Speech to be healthy (30s)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}

# 3. Health check Fish-Speech
Write-Host ""
Write-Host "🏥 Health check Fish-Speech..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Fish-Speech is healthy" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Fish-Speech may not be ready yet" -ForegroundColor Yellow
        Start-Sleep -Seconds 20
    }
} catch {
    Write-Host "⚠️  Cannot reach Fish-Speech, retrying in 20s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 20
}

# 4. Load environment
Write-Host ""
Write-Host "📋 Loading environment..." -ForegroundColor Cyan

if (Test-Path .env) {
    # Load .env manually for PowerShell (simple parser)
    Get-Content .env | Where-Object { $_ -notmatch '^\s*$' -and $_ -notmatch '^\s*#' } | ForEach-Object {
        $name, $value = $_ -split '=', 2
        if ($name -and $value) {
            [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "User")
        }
    }
    Write-Host "✅ .env loaded" -ForegroundColor Green
} else {
    Write-Host "⚠️  .env not found. Using defaults" -ForegroundColor Yellow
}

# 5. Run E2E pipeline test
Write-Host ""
Write-Host "🌊 Running E2E Pipeline Test..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

python examples/test_e2e_pipeline.py

Write-Host ""
Write-Host "✨ Test complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Check results above"
Write-Host "   2. Run demo: python examples/demo_conversation.py"
Write-Host "   3. Interactive: python examples/test_voice.py"
Write-Host ""
Write-Host "🧊 Stop Fish-Speech:" -ForegroundColor Yellow
Write-Host "   docker stop fish-speech && docker rm fish-speech"
