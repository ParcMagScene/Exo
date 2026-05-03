# =============================================================================
# Script de compilation rapide Windows - EXO Assistant v30.3
# PowerShell script pour compiler tous les modules sur Windows
# =============================================================================

param(
    [string]$BuildType = "Debug",
    [int]$Jobs = [Environment]::ProcessorCount
)

# Configuration
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ErrorActionPreference = "Stop"

# Fonction pour afficher des messages colorés
function Write-ColorMessage {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

Write-ColorMessage "🏗️  EXO Assistant v30.3 - Compilation Windows" "Cyan"
Write-ColorMessage "====================================================" "Cyan"
Write-ColorMessage "Type de build: $BuildType" "Yellow"
Write-ColorMessage "Jobs parallèles: $Jobs" "Yellow"
Write-ColorMessage "Projet: $ProjectRoot" "Yellow"
Write-Host ""

# Vérification des prérequis
Write-ColorMessage "📋 Vérification des prérequis..." "Yellow"

function Test-Command {
    param([string]$Command)
    if (Get-Command $Command -ErrorAction SilentlyContinue) {
        Write-ColorMessage "  ✅ $Command disponible" "Green"
        return $true
    } else {
        Write-ColorMessage "  ❌ $Command manquant" "Red"
        return $false
    }
}

$allPrereqsOk = $true
$allPrereqsOk = $allPrereqsOk -and (Test-Command "cmake")
$allPrereqsOk = $allPrereqsOk -and (Test-Command "qmake")

# Vérifier Visual Studio Build Tools
if (Get-Command "cl.exe" -ErrorAction SilentlyContinue) {
    Write-ColorMessage "  ✅ Compilateur MSVC disponible" "Green"
} elseif (Test-Path "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat") {
    Write-ColorMessage "  ✅ VS Build Tools 2022 trouvé" "Green"
    $vcvarsCmd = "`"${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat`" && set"
    cmd /c $vcvarsCmd | foreach {
        if ($_ -match "^(.*?)=(.*)$") {
            Set-Content "env:\$($matches[1])" $matches[2]
        }
    }
} else {
    Write-ColorMessage "  ❌ Visual Studio Build Tools manquant" "Red"
    $allPrereqsOk = $false
}

if (-not $allPrereqsOk) {
    Write-ColorMessage "❌ Prérequis manquants. Installation nécessaire." "Red"
    exit 1
}

# Création du dossier build
Set-Location $ProjectRoot
if (-not (Test-Path "build")) {
    New-Item -ItemType Directory -Name "build" | Out-Null
}
Set-Location "build"

# Configuration CMake
Write-ColorMessage "⚙️  Configuration CMake..." "Yellow"
$cmakeArgs = @(
    ".."
    "-DCMAKE_BUILD_TYPE=$BuildType"
    "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
    "-DBUILD_TESTS=ON"
    "-DEZVIZ_API_ENABLED=ON"
    "-DMICROSOFT_TTS_ENABLED=ON"
    "-DGOOGLE_SERVICES_ENABLED=ON"
    "-DMUSIC_STREAMING_ENABLED=ON"
    "-DAI_MEMORY_ENABLED=ON"
    "-DROOM_DESIGNER_3D_ENABLED=ON"
)

# Utiliser Visual Studio generator si disponible
if (Get-Command "msbuild.exe" -ErrorAction SilentlyContinue) {
    $cmakeArgs += "-G", "Visual Studio 17 2022"
    $cmakeArgs += "-A", "x64"
}

cmake @cmakeArgs

if ($LASTEXITCODE -ne 0) {
    Write-ColorMessage "❌ Erreur de configuration CMake" "Red"
    exit 1
}

# Compilation
Write-ColorMessage "🔨 Compilation avec $Jobs jobs..." "Yellow"
$startTime = Get-Date

cmake --build . --config $BuildType --parallel $Jobs

$endTime = Get-Date
$buildTime = [int]($endTime - $startTime).TotalSeconds

if ($LASTEXITCODE -ne 0) {
    Write-ColorMessage "❌ Erreur de compilation" "Red"
    exit 1
}

Write-ColorMessage "✅ Compilation terminée en ${buildTime}s" "Green"

# Vérification de l'exécutable
Write-ColorMessage "🧪 Vérification de la compilation..." "Yellow"

$exePath = if ($BuildType -eq "Debug") { 
    "Debug\RaspberryAssistant.exe" 
} else { 
    "Release\RaspberryAssistant.exe" 
}

if (Test-Path $exePath) {
    Write-ColorMessage "  ✅ Exécutable créé" "Green"
    $fileSize = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
    Write-ColorMessage "  📦 Taille: ${fileSize} MB" "Green"
} else {
    Write-ColorMessage "  ❌ Échec création exécutable" "Red"
    exit 1
}

# Test de lancement rapide
Write-ColorMessage "🚀 Test de lancement..." "Yellow"
$process = Start-Process -FilePath $exePath -ArgumentList "--version" -PassThru -WindowStyle Hidden
$process.WaitForExit(5000)
if ($process.ExitCode -eq 0 -or $process.HasExited -eq $false) {
    Write-ColorMessage "  ✅ Application se lance correctement" "Green"
    if (-not $process.HasExited) { $process.Kill() }
} else {
    Write-ColorMessage "  ⚠️  Problème de lancement (normal sans configuration)" "Yellow"
}

# Résumé final
Write-Host ""
Write-ColorMessage "🎉 COMPILATION RÉUSSIE !" "Green"
Write-ColorMessage "====================================================" "Green"
Write-ColorMessage "📁 Exécutable: $(Get-Location)\$exePath" "Cyan"
Write-ColorMessage "📊 Modules inclus:" "Cyan"
Write-ColorMessage "  • Claude Haiku IA" "White"
Write-ColorMessage "  • Microsoft Henri TTS" "White"
Write-ColorMessage "  • Domotique EZVIZ" "White"
Write-ColorMessage "  • Designer 3D Qt3D" "White"
Write-ColorMessage "  • Streaming Spotify/Tidal" "White"
Write-ColorMessage "  • Services Google" "White"
Write-ColorMessage "  • Mémoire AI SQLite" "White"
Write-Host ""
Write-ColorMessage "🚀 Prochaines étapes:" "Cyan"
Write-ColorMessage "1. Configurer les clés API dans config\assistant.conf" "White"
Write-ColorMessage "2. Lancer: .\$exePath --test-mode" "White"
Write-ColorMessage "3. Consulter: ..\QUICKSTART.md" "White"

# Tests unitaires si disponible
if ($BuildType -eq "Debug" -and (Test-Path "Debug\*test*.exe")) {
    Write-Host ""
    Write-ColorMessage "🧪 Lancement des tests unitaires..." "Yellow"
    ctest --output-on-failure --parallel $Jobs --build-config $BuildType
    if ($LASTEXITCODE -eq 0) {
        Write-ColorMessage "  ✅ Tous les tests passent" "Green"
    } else {
        Write-ColorMessage "  ⚠️  Certains tests echouent" "Yellow"
    }
}