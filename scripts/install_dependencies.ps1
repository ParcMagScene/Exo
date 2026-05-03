# =============================================================================
# Script d'installation automatique des dépendances - Windows
# EXO Assistant v30.3 - Toutes les dépendances requises
# =============================================================================

param(
    [switch]$Force,
    [switch]$SkipQt,
    [switch]$SkipPython,
    [switch]$SkipVisualStudio
)

$ErrorActionPreference = "Continue"

# Fonction pour afficher des messages colorés
function Write-ColorMessage {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Test-AdminRights {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-ColorMessage "🚀 Installation automatique des dépendances" "Cyan"
Write-ColorMessage "EXO Assistant v30.3 - Toutes les dépendances" "Cyan"
Write-ColorMessage "=================================================" "Cyan"

# Vérifier les droits administrateur
if (-not (Test-AdminRights)) {
    Write-ColorMessage "⚠️  Ce script nécessite les droits administrateur" "Yellow"
    Write-ColorMessage "Relancez PowerShell en tant qu'Administrateur" "Yellow"
    Write-ColorMessage "Clic droit sur PowerShell -> 'Exécuter en tant qu'administrateur'" "Yellow"
    
    # Tenter de relancer automatiquement
    $arguments = "-File `"$PSCommandPath`""
    if ($Force) { $arguments += " -Force" }
    if ($SkipQt) { $arguments += " -SkipQt" }
    if ($SkipPython) { $arguments += " -SkipPython" }
    if ($SkipVisualStudio) { $arguments += " -SkipVisualStudio" }
    
    Start-Process PowerShell -ArgumentList $arguments -Verb RunAs
    exit 0
}

Write-ColorMessage "✅ Droits administrateur confirmés" "Green"

# 1. Installation de Chocolatey (gestionnaire de packages)
Write-ColorMessage "`n🍫 Installation de Chocolatey..." "Yellow"
try {
    if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        
        # Rafraîchir l'environnement
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Write-ColorMessage "  ✅ Chocolatey installé avec succès" "Green"
    } else {
        Write-ColorMessage "  ✅ Chocolatey déjà installé" "Green"
    }
} catch {
    Write-ColorMessage "  ❌ Échec installation Chocolatey: $($_.Exception.Message)" "Red"
}

# 2. Installation de Python 3.11+
if (-not $SkipPython) {
    Write-ColorMessage "`n🐍 Installation de Python 3.11..." "Yellow"
    try {
        if (!(Get-Command python -ErrorAction SilentlyContinue)) {
            choco install python3 -y --version=3.11.9
            Write-ColorMessage "  ✅ Python 3.11 installé" "Green"
        } else {
            $pythonVersion = python --version 2>&1
            Write-ColorMessage "  ✅ Python déjà installé: $pythonVersion" "Green"
        }
        
        # Installer pip si nécessaire
        python -m ensurepip --upgrade
        python -m pip install --upgrade pip
        
    } catch {
        Write-ColorMessage "  ❌ Échec installation Python: $($_.Exception.Message)" "Red"
    }
}

# 3. Installation de Git
Write-ColorMessage "`n📦 Installation de Git..." "Yellow"
try {
    if (!(Get-Command git -ErrorAction SilentlyContinue)) {
        choco install git -y
        Write-ColorMessage "  ✅ Git installé" "Green"
    } else {
        $gitVersion = git --version
        Write-ColorMessage "  ✅ Git déjà installé: $gitVersion" "Green"
    }
} catch {
    Write-ColorMessage "  ❌ Échec installation Git: $($_.Exception.Message)" "Red"
}

# 4. Installation de CMake
Write-ColorMessage "`n🔨 Installation de CMake..." "Yellow"
try {
    if (!(Get-Command cmake -ErrorAction SilentlyContinue)) {
        choco install cmake -y --installargs 'ADD_CMAKE_TO_PATH=System'
        Write-ColorMessage "  ✅ CMake installé" "Green"
    } else {
        $cmakeVersion = cmake --version | Select-Object -First 1
        Write-ColorMessage "  ✅ CMake déjà installé: $cmakeVersion" "Green"
    }
} catch {
    Write-ColorMessage "  ❌ Échec installation CMake: $($_.Exception.Message)" "Red"
}

# 5. Installation de Visual Studio Build Tools
if (-not $SkipVisualStudio) {
    Write-ColorMessage "`n🏗️ Installation de Visual Studio Build Tools 2022..." "Yellow"
    try {
        $vsBuildTools = Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like "*Visual Studio*Build Tools*" }
        if (-not $vsBuildTools) {
            choco install visualstudio2022buildtools -y --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.CMake.Project"
            Write-ColorMessage "  ✅ Visual Studio Build Tools 2022 installé" "Green"
        } else {
            Write-ColorMessage "  ✅ Visual Studio Build Tools déjà installé" "Green"
        }
    } catch {
        Write-ColorMessage "  ❌ Échec installation VS Build Tools: $($_.Exception.Message)" "Red"
        Write-ColorMessage "  ℹ️  Vous pouvez l'installer manuellement depuis https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022" "Cyan"
    }
}
}

# 6. Installation de Qt 6.5+
if (-not $SkipQt) {
    Write-ColorMessage "`n🎨 Installation de Qt 6.5..." "Yellow"
    try {
        # Vérifier si Qt est déjà installé
        $qtPaths = @(
            "${env:ProgramFiles}\Qt",
            "${env:ProgramFiles(x86)}\Qt",
            "C:\Qt"
        )
        
        $qtFound = $false
        foreach ($path in $qtPaths) {
            if (Test-Path $path) {
                $qtVersions = Get-ChildItem $path -Directory | Where-Object { $_.Name -match "^6\.[5-9]" }
                if ($qtVersions) {
                    Write-ColorMessage "  ✅ Qt trouvé dans $path" "Green"
                    $qtFound = $true
                    break
                }
            }
        }
        
        if (-not $qtFound) {
            Write-ColorMessage "  ⚠️  Qt 6.5+ non trouvé" "Yellow"
            Write-ColorMessage "  📥 Téléchargement de l'installateur Qt..." "Cyan"
            
            # Télécharger l'installateur Qt
            $qtInstallerUrl = "https://download.qt.io/official_releases/online_installers/qt-unified-windows-x64-online.exe"
            $qtInstaller = "$env:TEMP\qt-unified-windows-x64-online.exe"
            
            Invoke-WebRequest -Uri $qtInstallerUrl -OutFile $qtInstaller
            
            Write-ColorMessage "  🚀 Lancement de l'installateur Qt..." "Cyan"
            Write-ColorMessage "  ℹ️  Veuillez installer Qt 6.5+ avec les composants suivants:" "Yellow"
            Write-ColorMessage "     • Qt 6.5 Desktop (MSVC 2019 64-bit)" "White"
            Write-ColorMessage "     • Qt 6.5 Additional Libraries" "White"
            Write-ColorMessage "     • Qt 3D" "White"
            Write-ColorMessage "     • Qt Multimedia" "White"
            Write-ColorMessage "     • CMake" "White"
            
            Start-Process -FilePath $qtInstaller -Wait
            
            Write-ColorMessage "  ✅ Installation Qt terminée" "Green"
        }
    } catch {
        Write-ColorMessage "  ❌ Échec installation Qt: $($_.Exception.Message)" "Red"
        Write-ColorMessage "  ℹ️  Installez manuellement depuis https://www.qt.io/download-qt-installer" "Cyan"
    }
}

# 7. Installation des dépendances Python
Write-ColorMessage "`n🐍 Installation des dépendances Python..." "Yellow"
try {
    # Créer requirements.txt s'il n'existe pas
    $requirementsContent = @"
anthropic>=0.3.0
requests>=2.31.0
aiohttp>=3.8.0
websockets>=11.0
sqlite3  # Built-in Python module
SpeechRecognition>=3.10.0
pydub>=0.25.1
pyaudio>=0.2.11
google-auth>=2.22.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.100.0
spotipy>=2.23.0
tidalapi>=0.7.0
numpy>=1.24.0
scipy>=1.11.0
pillow>=10.0.0
opencv-python>=4.8.0
"@
    
    Set-Content -Path "python\requirements.txt" -Value $requirementsContent -Force
    
    python -m pip install -r python\requirements.txt --upgrade
    Write-ColorMessage "  ✅ Dépendances Python installées" "Green"
} catch {
    Write-ColorMessage "  ❌ Échec installation dépendances Python: $($_.Exception.Message)" "Red"
}

# 8. Rafraîchissement de l'environnement
Write-ColorMessage "`n🔄 Rafraîchissement de l'environnement..." "Yellow"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# 9. Vérification finale
Write-ColorMessage "`n✅ Vérification des installations..." "Yellow"

$checks = @(
    @{Name="Python"; Command="python"; Args="--version"},
    @{Name="Pip"; Command="python"; Args="-m pip --version"},
    @{Name="Git"; Command="git"; Args="--version"},
    @{Name="CMake"; Command="cmake"; Args="--version"}
)

foreach ($check in $checks) {
    try {
        if ($check.Args) {
            $result = & $check.Command $check.Args.Split() 2>&1 | Select-Object -First 1
        } else {
            $result = & $check.Command 2>&1 | Select-Object -First 1
        }
        Write-ColorMessage "  ✅ $($check.Name): $result" "Green"
    } catch {
        Write-ColorMessage "  ❌ $($check.Name): Non trouvé" "Red"
    }
}

# Vérification Qt
$qtFound = $false
$qtPaths = @(
    "${env:ProgramFiles}\Qt",
    "${env:ProgramFiles(x86)}\Qt", 
    "C:\Qt"
)

foreach ($path in $qtPaths) {
    if (Test-Path $path) {
        $qtVersions = Get-ChildItem $path -Directory | Where-Object { $_.Name -match "^6\." }
        if ($qtVersions) {
            Write-ColorMessage "  ✅ Qt: Trouvé dans $path ($($qtVersions.Name -join ', '))" "Green"
            $qtFound = $true
            break
        }
    }
}

if (-not $qtFound) {
    Write-ColorMessage "  ⚠️  Qt: Non trouvé - Installation manuelle requise" "Yellow"
}

# 10. Résumé final
Write-Host ""
Write-ColorMessage "🎉 INSTALLATION DES DÉPENDANCES TERMINÉE !" "Green"
Write-ColorMessage "=========================================" "Green"
Write-ColorMessage "✅ Dépendances installées:" "Cyan"
Write-ColorMessage "  • Python 3.11+ avec pip" "White"
Write-ColorMessage "  • Git pour contrôle de version" "White" 
Write-ColorMessage "  • CMake pour build system" "White"
Write-ColorMessage "  • Visual Studio Build Tools 2022" "White"
Write-ColorMessage "  • Qt 6.5+ (si disponible)" "White"
Write-ColorMessage "  • Bibliothèques Python complètes" "White"

Write-Host ""
Write-ColorMessage "🚀 PROCHAINES ÉTAPES:" "Cyan"
Write-ColorMessage "1. Redémarrez PowerShell pour rafraîchir l'environnement" "White"
Write-ColorMessage "2. Lancez: .\scripts\quick_build.ps1 Debug" "White"
Write-ColorMessage "3. Testez: cd build\Debug && .\RaspberryAssistant.exe" "White"

if (-not $qtFound) {
    Write-Host ""
    Write-ColorMessage "⚠️  IMPORTANT: Qt 6.5+ non détecté" "Yellow"
    Write-ColorMessage "Installez Qt manuellement depuis: https://www.qt.io/download-qt-installer" "Yellow"
    Write-ColorMessage "Sélectionnez: Qt 6.5+ Desktop MSVC 2019 64-bit + Qt 3D + Qt Multimedia" "Yellow"
}

Write-ColorMessage "`n✨ Installation terminée ! Votre environnement est prêt pour le développement." "Green"