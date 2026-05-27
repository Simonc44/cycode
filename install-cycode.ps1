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
$APP_NAME = "CyCode"
$BASE_DIR = "$HOME\.cycode"
$BIN_DIR  = "$BASE_DIR\bin"
$REPO_DIR = "$BASE_DIR\repo"
$VENV_DIR = "$BASE_DIR\venv"
$REPO_URL = "https://github.com/Simonc44/cycode.git"

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

# Vérifie que Python >= 3.8
$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Impossible de déterminer la version de Python."
    exit 1
}
$pyParts = $pyVersion.Trim().Split('.')
$pyMajor = [int]$pyParts[0]
$pyMinor = [int]$pyParts[1]
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
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec de 'git fetch'."; Pop-Location; exit 1 }
    git pull --quiet
    if ($LASTEXITCODE -ne 0) { Write-Error "Échec de 'git pull'."; Pop-Location; exit 1 }
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

# ── 5. Création des launchers ─────────────────────────────────────────────────
Write-Step "Création des launchers..."

# Launcher .bat (compatible cmd et PowerShell via PATHEXT)
$batPath = "$BIN_DIR\cycode.bat"
@(
    '@echo off'
    "set CYCODE_HOME=$BASE_DIR"
    "`"$python`" -m cycode.main %*"
) | Set-Content -Path $batPath -Encoding Ascii

# Launcher .ps1 (natif PowerShell, évite les problèmes PATHEXT)
$ps1Path = "$BIN_DIR\cycode.ps1"
@(
    "`$env:CYCODE_HOME = '$BASE_DIR'"
    "& `"$python`" -m cycode.main @args"
) | Set-Content -Path $ps1Path -Encoding UTF8

Write-Host "  Launcher .bat : $batPath" -ForegroundColor DarkGray
Write-Host "  Launcher .ps1 : $ps1Path" -ForegroundColor DarkGray

# ── 6. Mise à jour du PATH utilisateur + session courante ────────────────────
Write-Step "Configuration du PATH..."

$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$BIN_DIR*") {
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$BIN_DIR", "User")
    Write-Host "  '$BIN_DIR' ajouté au PATH utilisateur." -ForegroundColor DarkGray
} else {
    Write-Host "  PATH utilisateur déjà configuré." -ForegroundColor DarkGray
}

# Rafraîchit le PATH dans la session PowerShell courante immédiatement
$machinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$freshUserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$env:PATH = "$machinePath;$freshUserPath"
Write-Host "  PATH de la session courante rechargé." -ForegroundColor DarkGray

# ── 7. Vérification PATHEXT ───────────────────────────────────────────────────
$pathExt = [Environment]::GetEnvironmentVariable("PATHEXT", "Machine")
if ($pathExt -notlike "*.BAT*") {
    Write-Warning "PATHEXT ne contient pas .BAT — utilisez 'cycode.ps1' si 'cycode' ne fonctionne pas."
}

# ── 8. Vérification finale ────────────────────────────────────────────────────
Write-Step "Vérification de l'installation..."

$resolved = Get-Command cycode -ErrorAction SilentlyContinue
if ($resolved) {
    Write-Host "  'cycode' trouvé : $($resolved.Source)" -ForegroundColor DarkGray
} else {
    Write-Host "  Avertissement : 'cycode' non résolu dans cette session." -ForegroundColor DarkYellow
    Write-Host "  Essayez : & `"$ps1Path`"" -ForegroundColor DarkYellow
}

# ── Terminé ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "$([char]0x2705) Installation de $APP_NAME ($Target) terminée avec succès !" -ForegroundColor Green
Write-Host ""
Write-Host "Vous pouvez maintenant utiliser " -NoNewline
Write-Host "cycode" -ForegroundColor Cyan -NoNewline
Write-Host " dans ce terminal ou tout nouveau terminal."
Write-Host "Si la commande n'est pas reconnue, exécutez : " -NoNewline
Write-Host ". `$PROFILE" -ForegroundColor Cyan -NoNewline
Write-Host " ou redémarrez votre terminal."
