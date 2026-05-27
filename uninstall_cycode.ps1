$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "CyCode Engine - Désinstallation"

# !! CRITIQUE : se placer dans $HOME immédiatement
# Windows verrouille tout dossier où un terminal est ouvert
Set-Location $HOME

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
        if (Test-Path $Path) {
            Write-Host "`n  $([char]0x26A0)  $Desc — toujours verrouillé, suppression manuelle requise." -ForegroundColor DarkYellow
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

Write-Host "`nDésinstallation en cours..." -ForegroundColor Cyan

$steps = @(
    @{
        Label  = "Désinstallation pip (venv)"
        Action = {
            $pip = "$venvDir\Scripts\pip.exe"
            if (Test-Path $pip) {
                # Désactive temporairement Stop pour les warnings natifs pip
                $prev = $ErrorActionPreference
                $ErrorActionPreference = "SilentlyContinue"
                $result = & $pip uninstall cycode -y 2>&1
                $ErrorActionPreference = $prev

                if ($LASTEXITCODE -ne 0 -and ($result -notmatch "not installed")) {
                    Write-Host "`n  $([char]0x26A0)  pip : $result" -ForegroundColor DarkYellow
                } else {
                    Write-Host "`n  $([char]0x2714)  Package pip désinstallé (ou déjà absent)." -ForegroundColor DarkGray
                }
            } else {
                Write-Host "`n  $([char]0x2012)  pip venv introuvable (ignoré)." -ForegroundColor DarkGray
            }
        }
    },
    @{
        Label  = "Suppression du répertoire principal"
        Action = {
            if (Test-Path $baseDir) {
                # Vide d'abord avec robocopy pour contourner les verrous Windows
                $tmp = New-Item -ItemType Directory -Path "$env:TEMP\cycode_empty_tmp" -Force
                robocopy "$($tmp.FullName)" $baseDir /MIR /NFL /NDL /NJH /NJS 2>&1 | Out-Null
                Remove-Item $tmp.FullName -Force -ErrorAction SilentlyContinue
            }
            Remove-IfExists $baseDir "Répertoire principal (~\.cycode)"
        }
    },
    @{
        Label  = "Suppression config Cygnis"
        Action = {
            Remove-IfExists "$HOME\.cygnis.json"   "Config (~\.cygnis.json)"
            Remove-IfExists "$HOME\.config\cygnis" "Config (~\.config\cygnis)"
        }
    },
    @{
        Label  = "Suppression de l'historique REPL"
        Action = {
            Remove-IfExists "$HOME\.cycode_history" "Historique REPL"
        }
    },
    @{
        Label  = "Suppression des exécutables système"
        Action = {
            @(
                "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts",
                "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
                "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts",
                "$env:APPDATA\Python\Python312\Scripts"
            ) | ForEach-Object {
                Remove-IfExists (Join-Path $_ "cycode.exe") "cycode.exe ($_)"
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
                $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";$cleaned"
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
            } else {
                Write-Host "`n  $([char]0x2012)  `$PROFILE introuvable (ignoré)." -ForegroundColor DarkGray
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

Write-Host ""
Write-Host "$([char]0x2705) CyCode a été supprimé proprement." -ForegroundColor Green
Write-Host "Fermez ce terminal — il pointait vers un dossier qui n'existe plus." -ForegroundColor DarkGray
