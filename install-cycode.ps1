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
  ██║      ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗
  ██║       ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝
  ╚██████╗   ██║   ╚██████╗╚██████╔╝██████╔╝███████╗
   ╚═════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"@ -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n>> $Message" -ForegroundColor Yellow
}

Clear-Host
Write-Logo

# --- Configuration ---
$APP_NAME  = "CyCode"
$BASE_DIR  = "$HOME\.cycode"
$BIN_DIR   = "$BASE_DIR\bin"
$REPO_DIR  = "$BASE_DIR\repo"          # séparé du venv et du bin
$VENV_DIR  = "$BASE_DIR\venv"
$REPO_URL  = "https://github.com/Simonc44/cycode.git"

Write-Host "--- Installation de $APP_NAME (cible : $Target) ---`n" -ForegroundColor Cyan

# ── 1. Vérifications système ──────────────────────────────────────────────────
Write-Step "Vérification des prérequis..."

if (-not [Environment]::Is64BitProcess) {
    Write-Error "$APP_NAME ne supporte pas le 32-bit. Utilisez Windows 64-bit."
    exit 1
}

foreach ($tool in @("git", "python")) {
    if (-not (Test-Command $tool)) {
        Write-Error "'$tool' est introuvable. Installez-le et relancez ce script."
        exit 1
    }
}

# Vérifie que Python ≥ 3.8
$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Impossible de déterminer la version de Python."
    exit 1
}
$pyMajor, $pyMinor = $pyVersion.Split('.') | ForEach-Object { [int]$_ }
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 8)) {
    Write-Error "Python 3.8+ requis (trouvé : $pyVersion)."
    exit 1
}
Write-Host "  Python $pyVersion détecté." -ForegroundColor DarkGray

# ── 2. Création des répertoires ───────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $BIN_DIR, $REPO_DIR | Out-Null

# ── 3. Synchronisation du dépôt ──────────────────────────────────────────────
Write-Step "Synchronisation du dépôt ($Target)..."

if (Test-Path "$REPO_DIR\.git") {
    Push-Location $REPO_DIR
    git fetch --quiet origin
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec de 'git fetch'."; exit 1 }
    git pull --quiet
    Pop-Location
} else {
    git clone --quiet $REPO_URL $REPO_DIR
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec du clonage du dépôt."; exit 1 }
}

# Checkout de la version demandée (sauf "latest")
if ($Target -ne "latest") {
    Push-Location $REPO_DIR
    $ref = if ($Target -eq "stable") { "stable" } else { "v$Target" }
    git checkout --quiet $ref 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tag/branche '$ref' introuvable dans le dépôt."
        Pop-Location; exit 1
    }
    Write-Host "  Checkout sur '$ref'." -ForegroundColor DarkGray
    Pop-Location
}

# ── 4. Environnement virtuel Python ──────────────────────────────────────────
Write-Step "Configuration de l'environnement Python..."

if (-not (Test-Path "$VENV_DIR\Scripts\python.exe")) {
    python -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec de la création du venv."; exit 1 }
}

$pip    = "$VENV_DIR\Scripts\pip.exe"
$python = "$VENV_DIR\Scripts\python.exe"

& $python -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "Échec de la mise à jour de pip."; exit 1 }

& $pip install -e $REPO_DIR --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "Échec de l'installation du paquet."; exit 1 }

# ── 5. Création du launcher ───────────────────────────────────────────────────
Write-Step "Création du launcher..."

$launcherPath = "$BIN_DIR\cycode.bat"

# Utilise Set-Content pour éviter les problèmes d'encodage avec Out-File
$batLines = @(
    '@echo off'
    "set CYCODE_HOME=$BASE_DIR"
    "`"$python`" -m cycode.main %*"
)
$batLines | Set-Content -Path $launcherPath -Encoding Ascii

Write-Host "  Launcher créé : $launcherPath" -ForegroundColor DarkGray

# ── 6. Mise à jour du PATH utilisateur ───────────────────────────────────────
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$BIN_DIR*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$BIN_DIR", "User")
    Write-Host "  '$BIN_DIR' ajouté au PATH utilisateur." -ForegroundColor DarkGray
} else {
    Write-Host "  PATH déjà configuré." -ForegroundColor DarkGray
}

# ── Terminé ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "$([char]0x2705) Installation de $APP_NAME ($Target) terminée avec succès !" -ForegroundColor Green
Write-Host "Redémarrez votre terminal puis tapez " -NoNewline
Write-Host "cycode" -ForegroundColor Cyan -NoNewline
Write-Host " pour lancer l'assistant."
