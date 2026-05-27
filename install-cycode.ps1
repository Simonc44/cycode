$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "CyCode Engine - Installation"
$Colors = @{ Accent="Cyan"; Success="Green"; Fail="Red"; Dim="DarkGray"; White="White" }

# --- Logo ASCII ---
function Write-Logo {
    Write-Host @"
   ██████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║      ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗  
  ██║       ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝  
  ╚██████╗   ██║   ╚██████╗╚██████╔╝██████╔╝███████╗
   ╚═════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"@ -ForegroundColor $Colors.Accent
}

Clear-Host
Write-Logo

# --- Fonction de progression ---
function Update-Install {
    param([int]$step, [string]$msg)
    Write-Progress -Activity "Installation de CyCode" -Status "Étape $step/4 : $msg" -PercentComplete ($step * 25)
}

# 1. Vérification
Update-Install 1 "Vérification des prérequis..."
if (!(Get-Command python -ErrorAction SilentlyContinue)) { Write-Host "Erreur: Python requis." -ForegroundColor $Colors.Fail; exit }
$baseDir = "$HOME\.cycode"
if (!(Test-Path $baseDir)) { New-Item -Path $baseDir -ItemType Directory | Out-Null }
Set-Location $baseDir

# 2. Sync
Update-Install 2 "Synchronisation du dépôt..."
$repoUrl = "https://github.com/Simonc44/cycode.git"
if (Test-Path ".git") { git pull | Out-Null } else { git clone $repoUrl . | Out-Null }

# 3. Environnement & Dépendances
Update-Install 3 "Configuration de l'environnement Python..."
if (!(Test-Path "venv")) { python -m venv venv }
. "$baseDir\venv\Scripts\Activate.ps1"
pip install --upgrade pip --quiet
pip install rich prompt-toolkit --quiet
pip install -e . --quiet

# 4. Finalisation
Update-Install 4 "Finalisation et création de l'alias..."
$cmd = "function cycode { & '$baseDir\venv\Scripts\activate'; python -m cycode.main }"
if (!(Test-Content -Path $PROFILE -Pattern "function cycode")) {
    $cmd | Out-File -FilePath $PROFILE -Append
}

# --- Fin ---
Write-Progress -Activity "Installation de CyCode" -Completed
Write-Host " [✅] Installation terminée avec succès !" -ForegroundColor $Colors.Success
Write-Host " [🚀] Tapez 'cycode' pour lancer l'assistant." -ForegroundColor $Colors.White
