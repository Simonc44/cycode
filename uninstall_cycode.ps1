$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "CyCode Engine - Désinstallation"

$baseDir    = "$HOME\.cycode"
$binDir     = "$baseDir\bin"
$venvDir    = "$baseDir\venv"

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
    param(
        [int]$Step,
        [int]$Total,
        [string]$Label
    )
    $pct     = [int](($Step / $Total) * 100)
    $filled  = [int](($pct / 100) * 40)
    $empty   = 40 - $filled
    $bar     = ("█" * $filled) + ("░" * $empty)

    # Efface la ligne courante et réécrit
    $pos = $Host.UI.RawUI.CursorPosition
    Write-Host "`r  [$bar] $pct%  $Label          " -NoNewline -ForegroundColor Cyan
    if ($Step -eq $Total) { Write-Host "" }   # saut de ligne final
}

# ── Suppression sécurisée avec rapport ───────────────────────────────────────
function Remove-IfExists {
    param([string]$Path, [string]$Desc)
    if (Test-Path $Path) {
        Remove-Item $Path -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  $([char]0x2714)  $Desc supprimé." -ForegroundColor DarkGray
    } else {
        Write-Host "  $([char]0x2012)  $Desc introuvable (ignoré)." -ForegroundColor DarkGray
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Clear-Host
Write-Logo

# Confirmation
$confirm = Read-Host "Êtes-vous certain de vouloir supprimer CyCode et toutes ses données ? (o/n)"
if ($confirm.Trim().ToLower() -ne "o") {
    Write-Host "`nDésinstallation annulée." -ForegroundColor Cyan
    exit 0
}

Write-Host ""

# Liste des étapes (label, scriptblock)
$steps = @(
    @{
        Label = "Désinstallation pip (venv)"
        Action = {
            $pip = "$venvDir\Scripts\pip.exe"
            if (Test-Path $pip) {
                & $pip uninstall cycode -y 2>&1 | Out-Null
            }
        }
    },
    @{
        Label = "Suppression du répertoire principal"
        Action = { Remove-IfExists $baseDir "Répertoire principal (~\.cycode)" }
    },
    @{
        Label = "Suppression config Cygnis"
        Action = {
            Remove-IfExists "$HOME\.cygnis.json"      "Config Cygnis (~\.cygnis.json)"
            Remove-IfExists "$HOME\.config\cygnis"    "Config Cygnis (~\.config\cygnis)"
        }
    },
    @{
        Label = "Suppression de l'historique REPL"
        Action = { Remove-IfExists "$HOME\.cycode_history" "Historique REPL" }
    },
    @{
        Label = "Suppression des exécutables système"
        Action = {
            # Cherche cycode.exe dans tous les dossiers Scripts Python connus
            $scriptsDirs = @(
                "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\Scripts",
                "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311\Scripts",
                "C:\Users\$env:USERNAME\AppData\Roaming\Python\Python312\Scripts",
                "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
            )
            foreach ($dir in $scriptsDirs) {
                $exe = Join-Path $dir "cycode.exe"
                Remove-IfExists $exe "Exécutable ($exe)"
            }
        }
    },
    @{
        Label = "Nettoyage du PATH utilisateur"
        Action = {
            $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
            if ($userPath -like "*$binDir*") {
                $cleaned = ($userPath.Split(';') | Where-Object { $_ -notlike "*\.cycode*" }) -join ';'
                [Environment]::SetEnvironmentVariable("PATH", $cleaned, "User")
                # Recharge dans la session courante
                $machinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
                $env:PATH = "$machinePath;$cleaned"
                Write-Host "  $([char]0x2714)  Entrée CyCode retirée du PATH." -ForegroundColor DarkGray
            } else {
                Write-Host "  $([char]0x2012)  PATH déjà propre (ignoré)." -ForegroundColor DarkGray
            }
        }
    },
    @{
        Label = "Nettoyage du profil PowerShell"
        Action = {
            if (Test-Path $PROFILE) {
                $lines    = Get-Content $PROFILE
                $filtered = $lines | Where-Object { $_ -notmatch "cycode" }
                if ($filtered.Count -ne $lines.Count) {
                    $filtered | Set-Content $PROFILE -Encoding UTF8
                    Write-Host "  $([char]0x2714)  Références cycode retirées de `$PROFILE." -ForegroundColor DarkGray
                } else {
                    Write-Host "  $([char]0x2012)  Aucune référence cycode dans `$PROFILE." -ForegroundColor DarkGray
                }
            }
        }
    }
)

$total = $steps.Count

Write-Host "Désinstallation en cours...`n" -ForegroundColor Cyan

for ($i = 0; $i -lt $total; $i++) {
    $step = $steps[$i]
    Show-Progress -Step $i -Total $total -Label $step.Label
    Start-Sleep -Milliseconds 120     # laisse le temps à la barre d'être visible
    & $step.Action
}

Show-Progress -Step $total -Total $total -Label "Terminé"
Start-Sleep -Milliseconds 200

# ── Résumé ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "$([char]0x2705) CyCode a été supprimé proprement." -ForegroundColor Green
Write-Host "Redémarrez votre terminal pour finaliser le nettoyage du PATH." -ForegroundColor DarkGray
