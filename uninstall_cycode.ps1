$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "CyCode Engine - Désinstallation"
$Colors = @{ Accent="Cyan"; Success="Green"; Fail="Red"; Dim="DarkGray"; White="White" }
$baseDir = "$HOME\.cycode"

function Write-Logo {
    Write-Host @"
   ██████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║      ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗  
  ██║       ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝  
  ╚██████╗   ██║   ╚██████╗╚██████╔╝██████╔╝███████╗
   ╚═════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"@ -ForegroundColor $Colors.Fail
    Write-Host "--- Désinstallation de CyCode ---`n" -ForegroundColor $Colors.Dim
}

Clear-Host
Write-Logo

# Confirmation
$confirm = Read-Host "Êtes-vous certain de vouloir supprimer CyCode et toutes ses données ? (o/n)"
if ($confirm -ne "o") { Write-Host "Désinstallation annulée." -ForegroundColor $Colors.Accent; exit }

$items = @(
    @{ path = $baseDir; desc = "Répertoire principal CyCode" },
    @{ path = "$HOME\.cygnis.json"; desc = "Config Cygnis 1" },
    @{ path = "$HOME\.config\cygnis"; desc = "Config Cygnis 2" },
    @{ path = "$HOME\.cycode_history"; desc = "Historique REPL" }
)

Write-Host "`nSuppression en cours..." -ForegroundColor $Colors.Accent

# Boucle de suppression avec barre de progression
for ($i = 0; $i -lt $items.Count; $i++) {
    $item = $items[$i]
    Write-Progress -Activity "Nettoyage CyCode" -Status "Suppression de : $($item.desc)" -PercentComplete (($i / $items.Count) * 100)
    
    if (Test-Path $item.path) {
        Remove-Item $item.path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Suppression de l'alias dans le profil
if (Test-Path $PROFILE) {
    $content = Get-Content $PROFILE
    $newContent = $content | Where-Object { $_ -notmatch "function cycode" }
    $newContent | Set-Content $PROFILE
}

Write-Progress -Activity "Nettoyage CyCode" -Completed
Write-Host "[✅] CyCode a été supprimé proprement." -ForegroundColor $Colors.Success
Write-Host "Le terminal a été nettoyé." -ForegroundColor $Colors.Dim
