# =============================================================================
# Script de test complet post-installation Qt
# EXO Assistant v30.3 - Validation finale environnement
# =============================================================================

Write-Host "TEST COMPLET DE L'ENVIRONNEMENT DE DEVELOPPEMENT" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

$testResults = @{}
$allTestsPassed = $true

# Fonction pour tester et enregistrer les resultats
function Test-Component {
    param([string]$Name, [scriptblock]$TestScript, [string]$ExpectedResult = "")
    
    Write-Host "`n🔍 Test: $Name" -ForegroundColor Yellow
    try {
        $result = & $TestScript
        if ($result) {
            Write-Host "  OK $Name - PASSE" -ForegroundColor Green
            if ($ExpectedResult) {
                Write-Host "     $result" -ForegroundColor Gray
            }
            $testResults[$Name] = $true
            return $true
        } else {
            Write-Host "  ECHEC $Name - FAIL" -ForegroundColor Red
            $testResults[$Name] = $false
            $script:allTestsPassed = $false
            return $false
        }
    } catch {
        Write-Host "  ERREUR $Name - $($_.Exception.Message)" -ForegroundColor Red
        $testResults[$Name] = $false
        $script:allTestsPassed = $false
        return $false
    }
}

# Rafraichir l'environnement
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "`n=== TESTS DES OUTILS DE BASE ===" -ForegroundColor Magenta

# Test Git
Test-Component "Git" {
    $version = git --version 2>$null
    return $version -and $version.Contains("git version")
}

# Test Python 3.11+
Test-Component "Python 3.11+" {
    $version = python --version 2>$null
    if ($version -and $version -match "Python 3\.1[1-9]") {
        return $version
    }
    return $false
}

# Test CMake
Test-Component "CMake" {
    $version = cmake --version 2>$null
    if ($version) {
        return ($version | Select-Object -First 1)
    }
    return $false
}

Write-Host "`n=== TESTS VISUAL STUDIO BUILD TOOLS ===" -ForegroundColor Magenta

# Test VS Build Tools
Test-Component "Visual Studio Build Tools" {
    $vsPaths = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    )
    
    foreach ($path in $vsPaths) {
        if (Test-Path $path) {
            return "Trouve: $path"
        }
    }
    return $false
}

# Test compilateur MSVC
Test-Component "Compilateur MSVC" {
    try {
        # Essayer de trouver cl.exe
        $clPath = Get-Command "cl.exe" -ErrorAction SilentlyContinue
        if ($clPath) {
            return "cl.exe disponible: $($clPath.Source)"
        }
        
        # Si pas dans PATH, chercher manuellement
        $vsPaths = @(
            "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
            "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe"
        )
        
        foreach ($pattern in $vsPaths) {
            $found = Get-ChildItem $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) {
                return "cl.exe trouve: $($found.FullName)"
            }
        }
        return $false
    } catch {
        return $false
    }
}

Write-Host "`n=== TESTS QT 6.5+ ===" -ForegroundColor Magenta

# Test Qt Installation
Test-Component "Qt 6.5+ Installation" {
    $qtPaths = @("C:\Qt", "${env:ProgramFiles}\Qt", "${env:ProgramFiles(x86)}\Qt")
    
    foreach ($qtPath in $qtPaths) {
        if (Test-Path $qtPath) {
            $qtVersions = Get-ChildItem $qtPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^6\.[5-9]" }
            if ($qtVersions) {
                $versionList = ($qtVersions.Name -join ', ')
                return "Versions trouvees: $versionList dans $qtPath"
            }
        }
    }
    return $false
}

# Test Qt qmake
Test-Component "Qt qmake" {
    $qtPaths = @("C:\Qt", "${env:ProgramFiles}\Qt", "${env:ProgramFiles(x86)}\Qt")
    
    foreach ($qtPath in $qtPaths) {
        if (Test-Path $qtPath) {
            $qtVersions = Get-ChildItem $qtPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^6\.[5-9]" }
            foreach ($version in $qtVersions) {
                $qmakePattern = Join-Path $qtPath "$($version.Name)\*\bin\qmake.exe"
                $qmakeFiles = Get-ChildItem $qmakePattern -ErrorAction SilentlyContinue
                if ($qmakeFiles) {
                    $qmakeFile = $qmakeFiles | Select-Object -First 1
                    return "qmake trouve: $($qmakeFile.FullName)"
                }
            }
        }
    }
    return $false
}

# Test Qt CMake
Test-Component "Qt CMake Integration" {
    $qtPaths = @("C:\Qt", "${env:ProgramFiles}\Qt", "${env:ProgramFiles(x86)}\Qt")
    
    foreach ($qtPath in $qtPaths) {
        if (Test-Path $qtPath) {
            $qtVersions = Get-ChildItem $qtPath -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^6\.[5-9]" }
            foreach ($version in $qtVersions) {
                $cmakePattern = Join-Path $qtPath "$($version.Name)\*\lib\cmake\Qt6"
                $cmakeDirs = Get-ChildItem $cmakePattern -Directory -ErrorAction SilentlyContinue
                if ($cmakeDirs) {
                    $cmakeDir = $cmakeDirs | Select-Object -First 1
                    return "Qt CMake trouve: $($cmakeDir.FullName)"
                }
            }
        }
    }
    return $false
}

Write-Host "`n=== TESTS PACKAGES PYTHON ===" -ForegroundColor Magenta

$pythonPackages = @{
    "anthropic" = "anthropic"
    "requests" = "requests"
    "aiohttp" = "aiohttp"  
    "websockets" = "websockets"
    "speech_recognition" = "speech_recognition"
    "pydub" = "pydub"
    "pyaudio" = "pyaudio"
    "google-auth" = "google.auth"
    "google-auth-oauthlib" = "google_auth_oauthlib"
    "google-api-python-client" = "googleapiclient"
    "spotipy" = "spotipy"
    "numpy" = "numpy"
    "scipy" = "scipy"
    "pillow" = "PIL"
    "opencv-python" = "cv2"
}

foreach ($package in $pythonPackages.GetEnumerator()) {
    Test-Component "Python $($package.Key)" {
        try {
            $result = python -c "import $($package.Value); print('OK')" 2>$null
            return $result -eq "OK"
        } catch {
            return $false
        }
    }
}

Write-Host "`n=== TEST API CLAUDE ===" -ForegroundColor Magenta

# Test configuration Claude API
Test-Component "Configuration Claude API" {
    if (Test-Path "config\assistant.conf") {
        $config = Get-Content "config\assistant.conf" -Raw
        if ($config -match "claude_api_key.*=.*sk-ant-api03-") {
            return "Cle API Claude configuree dans assistant.conf"
        }
    }
    return $false
}

# Test connectivite Claude API  
Test-Component "Connectivite Claude API" {
    try {
        $pythonCode = @"
import requests
try:
    response = requests.get('https://api.anthropic.com', timeout=5)
    if response.status_code < 500:
        print('Connexion OK')
    else:
        print('Erreur serveur')
except:
    print('Erreur connexion')
"@
        $result = python -c $pythonCode 2>$null
        return $result -eq "Connexion OK"
    } catch {
        return $false
    }
}

Write-Host "`n=== RESUME FINAL ===" -ForegroundColor Cyan
Write-Host "=================" -ForegroundColor Cyan

$passedTests = ($testResults.Values | Where-Object { $_ -eq $true }).Count
$totalTests = $testResults.Count
$failedTests = $totalTests - $passedTests

Write-Host "`nResultats des tests:" -ForegroundColor White
Write-Host "  OK Tests reussis: $passedTests" -ForegroundColor Green
Write-Host "  FAIL Tests echoues: $failedTests" -ForegroundColor Red
Write-Host "  TOTAL tests: $totalTests" -ForegroundColor Cyan

if ($allTestsPassed) {
    Write-Host "`nSUCCES - ENVIRONNEMENT PRET POUR LA COMPILATION !" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "Toutes les dependances sont correctement installees." -ForegroundColor Green
    Write-Host "Vous pouvez maintenant lancer la compilation :" -ForegroundColor White
    Write-Host "  .\scripts\quick_build.ps1 Debug" -ForegroundColor Yellow
} else {
    Write-Host "`nATTENTION - PROBLEMES DETECTES" -ForegroundColor Red
    Write-Host "=====================" -ForegroundColor Red
    Write-Host "Les dependances suivantes presentent des problemes :" -ForegroundColor Yellow
    
    foreach ($test in $testResults.GetEnumerator()) {
        if (-not $test.Value) {
            Write-Host "  • $($test.Key)" -ForegroundColor Red
        }
    }
    
    Write-Host "`nVerifiez les installations manquantes avant de compiler." -ForegroundColor Yellow
}

Write-Host "`nPour relancer ce test : .\scripts\test_environment.ps1" -ForegroundColor Cyan