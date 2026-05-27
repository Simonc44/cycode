$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "CyCode Engine - Désinstallation"

$baseDir = "$HOME\.cycode"
$binDir  = "$baseDir\bin"
$venvDir = "$baseDir\venv"

# ── Logo ──────────────────────────────────────────────────────────────────────
function Write-Logo {
    Write-Host @"
    ██████╗██╗  ██╗ ██████╗ ██████╗ ██████╗ ███████╗
  ██╔════╝╚██╗ ██╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║      ╚████╔╝ ██║     ██║   ██║██║  ██║█████╗
  ██║       ╚██╔╝  ██║     ██║   ██║██║  ██║██╔══╝
  ╚██████╗   ██║   ╚██████╗╚██████╔╝██████╔╝███████╗
   ╚═════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"@ -ForegroundColor Red
    Write-Host "--- Désinstallation de CyCode ---`n" -ForegroundColor DarkGray
}

# ── Barre de progression ──────────────────────────────────────────────────────
function Show-Progress {
    param([int]$Step, [int]$Total, [string]$Label)
    $pct    = [int](($Step / $Total) * 100)
    $filled = [int](($pct / 100) * 40)
    $empty  = 40 - $filled
    $bar    = ("█" * $filled) + ("░" * $empty)
    Write-Host "`r  [$bar] $pct%  $Label                    " -NoNewline -ForegroundColor Cyan
    if ($Step -eq $Total) { Write-Host "" }
}

# ── Suppression sécurisée ─────────────────────────────────────────────────────
function Remove-IfExists {
    param([string]$Path, [string]$Desc)
    if (Test-Path $Path) {
        Remove-Item $Path -Recurse -Force -ErrorAction SilentlyContinue
        # Vérifie que la suppression a bien eu lieu
        if (Test-Path $Path) {
            Write-Host "`n  $([char]0x26A0)  $Desc — impossible à supprimer (terminal ouvert dans ce dossier ?)." -ForegroundColor DarkYellow
        } else {
            Write-Host "`n  $([char]0x2714)  $Desc supprimé." -ForegroundColor DarkGray
        }
    } else {
        Write-Host "`n  $([char]0x2012)  $Desc introuvable (ignoré)." -ForegroundColor DarkGray
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Clear-Host
Write-Logo

$confirm = Read-Host "Êtes-vous certain de vouloir supprimer CyCode et toutes ses données ? (o/n)"
if ($confirm.Trim().ToLower() -ne "o") {
    Write-Host "`nDésinstallation annulée." -ForegroundColor Cyan
    exit 0
}

Write-Host ""

# !! CRITIQUE : quitter le répertoire AVANT toute suppression
# Si le terminal est dans ~\.cycode\*, Windows verrouille le dossier
Set-Location $HOME
Write-Host "  Répertoire de travail déplacé vers $HOME`n" -ForegroundColor DarkGray

$steps = @(
    @{
        Label  = "Désinstallation pip (venv)"
        Action = {
            $pip = "$venvDir\Scripts\pip.exe"
            if (Test-Path $pip) {
                & $pip uninstall cycode -y 2>&1 | Out-Null
                Write-Host "`n  $([char]0x2714)  Package pip désinstallé." -ForegroundColor DarkGray
            } else {
                Write-Host "`n  $([char]0x2012)  pip venv introuvable (ignoré)." -ForegroundColor DarkGray
            }
        }
    },
    @{
        Label  = "Suppression du répertoire principal"
        Action = {
            # Tente une suppression forcée avec robocopy (vide le dossier d'abord)
            # pour contourner les verrous résiduels
            if (Test-Path $baseDir) {
                $empty = New-Item -ItemType Directory -Path "$env:TEMP\cycode_empty_tmp" -Force
                robocopy "$($empty.FullName)" $baseDir /MIR /NFL /NDL /NJH /NJS 2>&1 | Out-Null
                Remove-Item $empty.FullName -Force -ErrorAction SilentlyContinue
            }
            Remove-IfExists $baseDir "Répertoire principal (~\.cycode)"
        }
    },
    @{
        Label  = "Suppression config Cygnis"
        Action = {
            Remove-IfExists "$HOME\.cygnis.json"   "Config Cygnis (~\.cygnis.json)"
            Remove-IfExists "$HOME\.config\cygnis" "Config Cygnis (~\.config\cygnis)"
        }
    },
    @{
        Label  = "Suppression de l'historique REPL"
        Action = { Remove-IfExists "$HOME\.cycode_history" "Historique REPL" }
    },
    @{
        Label  = "Suppression des exécutables système"
        Action = {
            $scriptsDirs = @(
                "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
                "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts",
                "$env:APPDATA\Python\Python312\Scripts",
                "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts"
            )
            foreach ($dir in $scriptsDirs) {
                Remove-IfExists (Join-Path $dir "cycode.exe") "cycode.exe ($dir)"
            }
        }
    },
    @{
        Label  = "Nettoyage du PATH utilisateur"
        Action = {
            $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
            if ($userPath -like "*\.cycode*") {
                $cleaned = ($userPath.Split(';') | Where-Object { $_ -notlike "*\.cycode*" }) -join ';'
                [Environment]::SetEnvironmentVariable("PATH", $cleaned, "User")
                $machinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
                $env:PATH = "$machinePath;$cleaned"
                Write-Host "`n  $([char]0x2714)  Entrées CyCode retirées du PATH." -ForegroundColor DarkGray
            } else {
                Write-Host "`n  $([char]0x2012)  PATH déjà propre (ignoré)." -ForegroundColor DarkGray
            }
        }
    },
    @{
        Label  = "Nettoyage du profil PowerShell"
        Action = {
            if (Test-Path $PROFILE) {
                $lines    = Get-Content $PROFILE
                $filtered = $lines | Where-Object { $_ -notmatch "cycode" }
                if ($filtered.Count -ne $lines.Count) {
                    $filtered | Set-Content $PROFILE -Encoding UTF8
                    Write-Host "`n  $([char]0x2714)  Références cycode retirées de `$PROFILE." -ForegroundColor DarkGray
                } else {
                    Write-Host "`n  $([char]0x2012)  Aucune référence cycode dans `$PROFILE." -ForegroundColor DarkGray
                }
            }
        }
    }
)

$total = $steps.Count

for ($i = 0; $i -lt $total; $i++) {
    Show-Progress -Step $i -Total $total -Label $steps[$i].Label
    Start-Sleep -Milliseconds 100
    & $steps[$i].Action
}

Show-Progress -Step $total -Total $total -Label "Terminé"

# ── Résumé ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "$([char]0x2705) CyCode a été supprimé proprement." -ForegroundColor Green
Write-Host "Fermez ce terminal — il pointait vers un dossier qui n'existe plus." -ForegroundColor DarkGray
