$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "CyCode Engine - Désinstallation"
$Colors = @{ Accent="Cyan"; Success="Green"; Fail="Red"; Dim="DarkGray"; White="White" }
$baseDir = "$HOME\.cycode"

function Write-Logo {
    Write-Host @"
    ██████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║     ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗  
  ██║      ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝  
  ╚██████╗  ██║   ╚██████╗╚██████╔╝██████╔╝███████╗
   ╚═════╝  ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"@ -ForegroundColor $Colors.Fail
    Write-Host "--- Désinstallation de CyCode ---`n" -ForegroundColor $Colors.Dim
}

Clear-Host
Write-Logo

# Confirmation
$confirm = Read-Host "Êtes-vous certain de vouloir supprimer CyCode et toutes ses données ? (o/n)"
if ($confirm -ne "o") { Write-Host "Désinstallation annulée." -ForegroundColor $Colors.Accent; exit }

Write-Host "`nSuppression en cours..." -ForegroundColor $Colors.Accent

# 1. Désinstallation via PIP
Write-Progress -Activity "Nettoyage CyCode" -Status "Désinstallation du package Python (pip)" -PercentComplete 20
pip uninstall cycode -y | Out-Null

# 2. Suppression des dossiers et fichiers
$items = @(
    @{ path = $baseDir; desc = "Répertoire principal CyCode" },
    @{ path = "$HOME\.cygnis.json"; desc = "Config Cygnis 1" },
    @{ path = "$HOME\.config\cygnis"; desc = "Config Cygnis 2" },
    @{ path = "$HOME\.cycode_history"; desc = "Historique REPL" }
)

for ($i = 0; $i -lt $items.Count; $i++) {
    $item = $items[$i]
    Write-Progress -Activity "Nettoyage CyCode" -Status "Suppression de : $($item.desc)" -PercentComplete (40 + ($i / $items.Count) * 30)
    
    if (Test-Path $item.path) {
        Remove-Item $item.path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# 3. Suppression de l'exécutable système (cycode.exe)
Write-Progress -Activity "Nettoyage CyCode" -Status "Suppression de l'exécutable système" -PercentComplete 80
$pyPath = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pyPath) {
    $scriptsDir = Join-Path (Split-Path $pyPath.Definition) "Scripts"
    $exePath = Join-Path $scriptsDir "cycode.exe"
    if (Test-Path $exePath) {
        Remove-Item $exePath -Force -ErrorAction SilentlyContinue
    }
}

# 4. Suppression de l'alias dans le profil utilisateur
if (Test-Path $PROFILE) {
    $content = Get-Content $PROFILE
    $newContent = $content | Where-Object { $_ -notmatch "cycode" }
    $newContent | Set-Content $PROFILE
}

Write-Progress -Activity "Nettoyage CyCode" -Completed
Write-Host "[✅] CyCode a été supprimé proprement." -ForegroundColor $Colors.Success
Write-Host "Le terminal a été nettoyé." -ForegroundColor $Colors.Dim
