param(
    [Parameter(Position=0)]
    [ValidatePattern('^(stable|latest|\d+\.\d+\.\d+(-[^\s]+)?)$')]
    [string]$Target = "latest"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = 'SilentlyContinue'

# --- Logo ASCII ---
function Write-Logo {
    Write-Host @"
    ██████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║     ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗  
  ██║      ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝  
  ╚██████╗  ██║   ╚██████╗╚██████╔╝██████╔╝███████╗
   ╚═════╝  ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"@ -ForegroundColor Cyan
}

Clear-Host
Write-Logo

# --- Configuration ---
$APP_NAME = "CyCode"
$BASE_DIR = "$HOME\.cycode"
$BIN_DIR = "$BASE_DIR\bin"
$DOWNLOAD_DIR = "$BASE_DIR\downloads"

New-Item -ItemType Directory -Force -Path $BIN_DIR, $DOWNLOAD_DIR | Out-Null

Write-Host "--- Installation de $APP_NAME ---" -ForegroundColor Cyan

# 1. Vérification système
if (-not [Environment]::Is64BitProcess) {
    Write-Error "$APP_NAME ne supporte pas le 32-bit. Utilisez un Windows 64-bit."
    exit 1
}

# 2. Synchronisation
Write-Output "Synchronisation des sources..."
$repoUrl = "https://github.com/Simonc44/cycode.git"
if (Test-Path "$BASE_DIR\.git") {
    Push-Location $BASE_DIR; git pull | Out-Null; Pop-Location
} else {
    git clone $repoUrl $BASE_DIR | Out-Null
}

# 3. Environnement
Write-Output "Configuration de l'environnement Python..."
$venvPath = "$BASE_DIR\venv"
if (!(Test-Path "$venvPath\Scripts\python.exe")) {
    python -m venv $venvPath
}

& "$venvPath\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$venvPath\Scripts\pip.exe" install -e . --quiet

# 4. Launcher (Bat)
$launcherPath = "$BIN_DIR\cycode.bat"
$batContent = @"
@echo off
"$venvPath\Scripts\python.exe" -m cycode.main %*
"@
$batContent | Out-File -FilePath $launcherPath -Encoding ascii

# Ajout au PATH utilisateur
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$BIN_DIR*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$BIN_DIR", "User")
    Write-Output "Ajout de $BIN_DIR au PATH utilisateur."
}

Write-Output ""
Write-Host "$([char]0x2705) Installation terminée avec succès !" -ForegroundColor Green
Write-Output "Redémarrez votre terminal et tapez 'cycode' pour lancer l'assistant."
