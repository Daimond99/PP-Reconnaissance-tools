# TheRecon — installer (Windows).
#
# Mirrors README.md's manual steps:
#   1. WSL2 + Ubuntu (if not already installed) -- needs a reboot the first
#      time, this script can't skip that, Windows enforces it
#   2. the 6 authorized tools inside WSL (nmap masscan hydra ncrack ncat
#      ruby -> evil-winrm via gem)
#   3. clone (or update) the repo, create a venv, install Python deps
#
# Usage (from an elevated PowerShell the first time, for step 1):
#   irm https://raw.githubusercontent.com/Daimond99/TheRecon/main/install.ps1 | iex
# or, from an already-cloned checkout:
#   .\install.ps1

$ErrorActionPreference = "Stop"

function Log($msg)  { Write-Host "`n[install.ps1] $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "`n[install.ps1] ERROR: $msg" -ForegroundColor Red; exit 1 }

# ---- 1. WSL2 -----------------------------------------------------------
# Same "any real distro, not just Docker Desktop's pseudo-entries" check
# terminal_tabs.py's _wsl_available() uses, so this script and the app
# agree on what counts as "WSL is usable".
function Test-WslReady {
    $wslExe = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wslExe) { return $false }
    try {
        $distros = (wsl.exe -l -q 2>$null) -replace "`0", "" |
            Where-Object { $_ -and $_ -notmatch "^docker-desktop" }
        return [bool]$distros
    } catch { return $false }
}

if (Test-WslReady) {
    Log "WSL already installed with a real distro -- skipping install/reboot step"
} else {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Fail "WSL isn't installed yet, and installing it needs Administrator. Re-run this script from an elevated PowerShell (Run as Administrator)."
    }
    Log "installing WSL2 + Ubuntu (this requires a reboot before continuing)"
    wsl --install -d Ubuntu
    Write-Host ""
    Write-Host "==> WSL install started. REBOOT NOW, open Ubuntu once to finish" -ForegroundColor Yellow
    Write-Host "    its first-run setup (creates your WSL user), then re-run" -ForegroundColor Yellow
    Write-Host "    this script to continue." -ForegroundColor Yellow
    exit 0
}

# ---- 2. The 6 tools, inside WSL -----------------------------------------
Log "installing the 6 authorized tools inside WSL (you may be prompted for your WSL sudo password)"
$toolScript = "sudo apt-get update && sudo apt-get install -y nmap masscan hydra ncrack ncat ruby ruby-dev python3 python3-pip python3-venv && sudo gem install evil-winrm"
wsl.exe -e bash -lc $toolScript
if ($LASTEXITCODE -ne 0) { Fail "tool install inside WSL failed (see output above)" }

Log "verifying tool versions"
wsl.exe -e bash -lc 'for t in nmap masscan hydra ncrack ncat; do printf "  %-10s %s\n" "$t" "$(command -v "$t" >/dev/null 2>&1 && $t --version 2>&1 | head -n1 || echo "NOT FOUND")"; done; printf "  %-10s %s\n" "evil-winrm" "$(command -v evil-winrm >/dev/null 2>&1 && evil-winrm --version 2>&1 | head -n1 || echo "NOT FOUND")"'

# ---- 3. Repo + Python deps (Windows side) -------------------------------
$RepoUrl = "https://github.com/Daimond99/TheRecon.git"
$ScriptDir = $PSScriptRoot
if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "CLAUDE.md")) -and (Test-Path (Join-Path $ScriptDir "requirements.txt"))) {
    $RepoDir = $ScriptDir
    Log "running from existing checkout: $RepoDir"
} else {
    $RepoDir = if ($env:THERECON_DIR) { $env:THERECON_DIR } else { Join-Path $HOME "TheRecon" }
    if (Test-Path (Join-Path $RepoDir ".git")) {
        Log "repo already at $RepoDir, pulling latest"
        git -C $RepoDir pull --ff-only
    } else {
        Log "cloning into $RepoDir"
        git clone $RepoUrl $RepoDir
    }
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) {
    Fail "python not found on PATH -- install Python 3.10+ from python.org first, then re-run this script"
}

Set-Location $RepoDir

Log "creating Python venv (.venv)"
if (-not (Test-Path ".venv")) {
    & $python.Source -m venv .venv
} else {
    Log ".venv already exists, reusing"
}

Log "installing Python deps"
& ".venv\Scripts\pip.exe" install --upgrade pip
& ".venv\Scripts\pip.exe" install -r requirements.txt

Log "done. run the app with:"
Write-Host ""
Write-Host "  cd '$RepoDir'"
Write-Host "  .venv\Scripts\activate"
Write-Host "  python -m src.main"
Write-Host ""
