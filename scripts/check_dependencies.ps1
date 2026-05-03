# =============================================================================
# Script de verification et installation complete des dependances
# EXO Assistant v30.3 - Verification systematique
# =============================================================================

Write-Host "VERIFICATION COMPLETE DES DEPENDANCES" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

$dependenciesStatus = @{}
$allDependenciesOk = $true

# Fonction pour afficher les resultats
function Show-Status {
    param([string]$Name, [bool]$IsInstalled, [string]$Version = "")
    if ($IsInstalled) {
        Write-Host "  ✅ $Name" -ForegroundColor Green -NoNewline
        if ($Version) { Write-Host " - $Version" -ForegroundColor White }
        else { Write-Host "" }
        $dependenciesStatus[$Name] = $true
    } else {
        Write-Host "  ❌ $Name - Non installe" -ForegroundColor Red
        $dependenciesStatus[$Name] = $false
        $script:allDependenciesOk = $false
    }
}

# Rafraichir l'environnement
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "`n1. VERIFICATION DES OUTILS DE BASE" -ForegroundColor Yellow
Write-Host "===================================" -ForegroundColor Yellow

# Git
try {
    $gitVersion = git --version 2>$null
    Show-Status "Git" $true $gitVersion
} catch {
    Show-Status "Git" $false
}

# Python 3.11+
try {
    $pythonVersion = python --version 2>$null
    if ($pythonVersion -match "Python 3\.1[1-9]") {
        Show-Status "Python 3.11+" $true $pythonVersion
    } else {
        Show-Status "Python 3.11+" $false "Version incorrecte: $pythonVersion"
    }
} catch {
    Show-Status "Python 3.11+" $false
}

# CMake
try {
    $cmakeVersion = cmake --version 2>$null | Select-Object -First 1
    Show-Status "CMake" $true $cmakeVersion
} catch {
    Show-Status "CMake" $false
}

Write-Host "`n2. VERIFICATION VISUAL STUDIO BUILD TOOLS" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Yellow

# Visual Studio Build Tools
$vsBuildToolsPaths = @(
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools",
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\BuildTools",
    "${env:ProgramFiles}\Microsoft Visual Studio\2019\BuildTools"
)

$vsFound = $false
foreach ($path in $vsBuildToolsPaths) {
    if (Test-Path "$path\VC\Auxiliary\Build\vcvars64.bat") {
        Show-Status "Visual Studio Build Tools" $true "Trouve dans $path"
        $vsFound = $true
        break
    }
}

if (-not $vsFound) {
    Show-Status "Visual Studio Build Tools" $false
}

# Chocolatey
try {
    $chocoVersion = choco --version 2>$null
    Show-Status "Chocolatey" $true "v$chocoVersion"
} catch {
    Show-Status "Chocolatey" $false
}

Write-Host "`n3. VERIFICATION QT 6.5+" -ForegroundColor Yellow
Write-Host "======================" -ForegroundColor Yellow

# Qt 6.5+
$qtPaths = @("C:\Qt", "${env:ProgramFiles}\Qt", "${env:ProgramFiles(x86)}\Qt")
$qtFound = $false

foreach ($qtPath in $qtPaths) {
    if (Test-Path $qtPath) {
        $qtVersions = Get-ChildItem $qtPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^6\.[5-9]" }
        if ($qtVersions) {
            $qtVersionList = ($qtVersions.Name -join ', ')
            Show-Status "Qt 6.5+" $true "Versions trouvees: $qtVersionList dans $qtPath"
            $qtFound = $true
            
            # Verifier les composants Qt essentiels
            foreach ($version in $qtVersions) {
                $qtBinPath = Join-Path $qtPath "$($version.Name)\msvc*\bin"
                $qtBinDirs = Get-ChildItem $qtBinPath -Directory -ErrorAction SilentlyContinue
                if ($qtBinDirs) {
                    $qmakePath = Join-Path $qtBinDirs[0].FullName "qmake.exe"
                    if (Test-Path $qmakePath) {
                        Show-Status "  Qt qmake" $true $qtBinDirs[0].FullName
                    }
                }
            }
            break
        }
    }
}

if (-not $qtFound) {
    Show-Status "Qt 6.5+" $false
}

Write-Host "`n4. VERIFICATION PACKAGES PYTHON" -ForegroundColor Yellow
Write-Host "===============================" -ForegroundColor Yellow

$pythonPackages = @(
    "anthropic",
    "requests", 
    "aiohttp",
    "websockets",
    "SpeechRecognition",
    "pydub",
    "pyaudio",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "spotipy",
    "numpy",
    "scipy",
    "pillow",
    "opencv-python"
)

foreach ($package in $pythonPackages) {
    try {
        $result = python -c "import $package; print('OK')" 2>$null
        if ($result -eq "OK") {
            Show-Status "Python $package" $true
        } else {
            Show-Status "Python $package" $false
        }
    } catch {
        Show-Status "Python $package" $false
    }
}

Write-Host "`n5. RESUME FINAL" -ForegroundColor Yellow
Write-Host "==============" -ForegroundColor Yellow

if ($allDependenciesOk) {
    Write-Host "🎉 TOUTES LES DEPENDANCES SONT INSTALLEES !" -ForegroundColor Green
    Write-Host "Vous pouvez maintenant proceder a la compilation." -ForegroundColor Green
} else {
    Write-Host "⚠️  DEPENDANCES MANQUANTES DETECTEES" -ForegroundColor Red
    Write-Host "Les dependances suivantes doivent etre installees :" -ForegroundColor Yellow
    
    foreach ($dep in $dependenciesStatus.GetEnumerator()) {
        if (-not $dep.Value) {
            Write-Host "  • $($dep.Key)" -ForegroundColor Red
        }
    }
    
    Write-Host "`nACTIONS REQUISES :" -ForegroundColor Cyan
    
    if (-not $dependenciesStatus["Chocolatey"]) {
        Write-Host "1. Installer Chocolatey :" -ForegroundColor White
        Write-Host "   Set-ExecutionPolicy Bypass -Scope Process -Force" -ForegroundColor Gray
        Write-Host "   iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))" -ForegroundColor Gray
    }
    
    if (-not $dependenciesStatus["Python 3.11+"]) {
        Write-Host "2. Installer Python 3.11 :" -ForegroundColor White
        Write-Host "   choco install python3 --version=3.11.9 -y" -ForegroundColor Gray
    }
    
    if (-not $dependenciesStatus["CMake"]) {
        Write-Host "3. Installer CMake :" -ForegroundColor White
        Write-Host "   choco install cmake -y --installargs 'ADD_CMAKE_TO_PATH=System'" -ForegroundColor Gray
    }
    
    if (-not $dependenciesStatus["Visual Studio Build Tools"]) {
        Write-Host "4. Installer Visual Studio Build Tools :" -ForegroundColor White
        Write-Host "   choco install visualstudio2022buildtools -y --package-parameters \"--add Microsoft.VisualStudio.Workload.VCTools\"" -ForegroundColor Gray
    }
    
    if (-not $dependenciesStatus["Qt 6.5+"]) {
        Write-Host "5. Installer Qt 6.5+ :" -ForegroundColor White
        Write-Host "   Telechargez depuis : https://www.qt.io/download-qt-installer" -ForegroundColor Gray
        Write-Host "   Selectionnez : Qt 6.5+ Desktop MSVC 2019 64-bit + Qt 3D + Qt Multimedia" -ForegroundColor Gray
    }
    
    $missingPythonPackages = @()
    foreach ($package in $pythonPackages) {
        if (-not $dependenciesStatus["Python $package"]) {
            $missingPythonPackages += $package
        }
    }
    
    if ($missingPythonPackages.Count -gt 0) {
        Write-Host "6. Installer packages Python manquants :" -ForegroundColor White
        Write-Host "   python -m pip install $($missingPythonPackages -join ' ')" -ForegroundColor Gray
    }
}

Write-Host "`nPour relancer cette verification : .\scripts\check_dependencies.ps1" -ForegroundColor Cyan