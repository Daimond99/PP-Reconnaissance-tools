# TheRecon - one-click installer (Windows).
#
# Prerequisite: WSL with a Linux distro already installed. Everything else is
# done here:
#   1. Python 3.10+ on Windows (winget, only if missing)
#   2. Docker Engine inside the WSL distro (apt, only if missing)
#   3. builds + starts the sandboxed tool container (docker/run.sh)
#   4. creates .venv and installs the Python packages
#   5. creates Start Menu + Desktop shortcuts that open TheRecon.bat
#
# Run it by double-clicking "Install TheRecon.bat", or from PowerShell:
#   .\install.ps1
#
# This file is ASCII-only on purpose: Windows PowerShell 5.1 reads a .ps1
# without a BOM as the ANSI code page, which garbles non-ASCII text.

$ErrorActionPreference = "Stop"

function Log($msg)  { Write-Host "`n[install] $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "`n[install] ERROR: $msg" -ForegroundColor Red; exit 1 }

# ---- 0. Where the repo lives ------------------------------------------
$RepoUrl = "https://github.com/Daimond99/PP-Reconnaissance-tools.git"
$ScriptDir = $PSScriptRoot
if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "CLAUDE.md")) -and (Test-Path (Join-Path $ScriptDir "requirements.txt"))) {
    $RepoDir = $ScriptDir
    Log "using this checkout: $RepoDir"
} else {
    $RepoDir = if ($env:THERECON_DIR) { $env:THERECON_DIR } else { Join-Path $HOME "TheRecon" }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Fail "git is not installed. Download the repo ZIP from GitHub, extract it, and run 'Install TheRecon.bat' inside that folder."
    }
    if (Test-Path (Join-Path $RepoDir ".git")) {
        Log "repo already at $RepoDir, pulling latest"
        git -C $RepoDir pull --ff-only
    } else {
        Log "cloning into $RepoDir"
        git clone $RepoUrl $RepoDir
    }
}
Set-Location $RepoDir

# ---- 1. WSL must already be installed (user does this step) -------------
Log "checking WSL"
& wsl.exe -e sh -c "exit 0" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "WSL with a Linux distro is not ready. Open PowerShell as Administrator and run: wsl --install -d Ubuntu  (reboot if asked, open Ubuntu once to create your user), then run 'Install TheRecon.bat' again."
}
$wslUser = (& wsl.exe -e sh -c "id -un" 2>$null | Out-String).Trim()
$wslDistro = (& wsl.exe -e sh -c "echo `$WSL_DISTRO_NAME" 2>$null | Out-String).Trim()
if (-not $wslUser -or -not $wslDistro) { Fail "could not read the WSL user or distro name" }
Log "WSL distro '$wslDistro', user '$wslUser'"

# ---- 2. Python 3.10+ on Windows ----------------------------------------
function Find-Python {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe")
    )
    foreach ($name in @("python", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates += $cmd.Source }
    }
    foreach ($exe in $candidates) {
        if (-not (Test-Path $exe)) { continue }
        $ver = (& $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and $ver -match '^3\.(\d+)$' -and [int]$matches[1] -ge 10) { return $exe }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Log "Python 3.10+ not found - installing Python 3.12 with winget"
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        Fail "winget not found. Install Python 3.12 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run 'Install TheRecon.bat' again."
    }
    & winget.exe install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    $python = Find-Python
    if (-not $python) { Fail "Python 3.12 install did not produce a usable python.exe. Run 'Install TheRecon.bat' again." }
}
Log "Windows Python: $python"

# ---- 3. Docker Engine inside WSL (native, NOT Docker Desktop) ----------
Log "checking Docker inside WSL"
$hasDocker = (& wsl.exe -e sh -c "command -v docker >/dev/null 2>&1 && echo yes || echo no" 2>$null | Out-String).Trim()
if ($hasDocker -ne "yes") {
    Log "installing docker.io inside WSL (apt, runs as root, a few minutes)"
    & wsl.exe -u root -e sh -c "export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get install -y docker.io"
    if ($LASTEXITCODE -ne 0) { Fail "apt install of docker.io failed (see output above)" }
}

# Start the daemon and make sure the WSL user is in the docker group.
& wsl.exe -u root -e sh -c "systemctl enable --now docker >/dev/null 2>&1 || service docker start >/dev/null 2>&1; usermod -aG docker $wslUser"

# Group membership only applies to new login sessions, so restart the distro
# once if this session is not in the group yet. Only the WSL distro restarts,
# not Windows.
$inGroup = (& wsl.exe -e sh -c "id -nG | tr ' ' '\n' | grep -qx docker && echo yes || echo no" 2>$null | Out-String).Trim()
if ($inGroup -ne "yes") {
    Log "restarting WSL distro '$wslDistro' so the docker group applies"
    & wsl.exe --terminate $wslDistro | Out-Null
    Start-Sleep -Seconds 3
}

& wsl.exe -e sh -c "docker info >/dev/null 2>&1"
if ($LASTEXITCODE -ne 0) {
    Fail "Docker is installed but not reachable from WSL. Open Ubuntu and run: sudo systemctl start docker  -- then run 'Install TheRecon.bat' again."
}

# ---- 4. Sandboxed tool container (docker/run.sh) ------------------------
function ConvertTo-WslPath($winPath) {
    $full = (Resolve-Path $winPath).Path
    $drive = $full.Substring(0, 1).ToLower()
    $rest = $full.Substring(2) -replace '\\', '/'
    return "/mnt/$drive$rest"
}
Log "building + starting the tool container (first run takes several minutes)"
$wslRepoDir = ConvertTo-WslPath $RepoDir
& wsl.exe -e bash -c "cd '$wslRepoDir/docker' && bash run.sh"
if ($LASTEXITCODE -ne 0) { Fail "docker/run.sh failed (see output above)" }

# ---- 5. Python venv + packages ------------------------------------------
Log "creating .venv"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "could not create .venv" }
} else {
    Log ".venv already exists, reusing"
}

Log "installing Python packages (requirements.txt)"
& .venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed (see output above)" }
& .venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed (see output above)" }

# ---- 6. Shortcuts that open the app without a console -------------------
# WScript.Shell cannot save a .lnk into a folder whose path has non-ASCII
# characters (OneDrive's Thai "Desktop" folder, for one). Save to the ASCII
# temp folder first, then move the finished file into place.
Log "creating Start Menu and Desktop shortcuts"
$launcher = Join-Path $RepoDir "TheRecon.bat"
$shell = New-Object -ComObject WScript.Shell
$tmpLnk = Join-Path $env:TEMP "TheRecon.lnk"
foreach ($dir in @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop"))) {
    $lnk = $shell.CreateShortcut($tmpLnk)
    $lnk.TargetPath = $launcher
    $lnk.WorkingDirectory = $RepoDir
    $lnk.WindowStyle = 7
    $lnk.Description = "TheRecon"
    $lnk.Save()
    Move-Item -LiteralPath $tmpLnk -Destination (Join-Path $dir "TheRecon.lnk") -Force
}

# ---- 7. Final check (informational, does not fail the install) ----------
Log "running preflight check"
& .venv\Scripts\python.exe -m src.preflight
if ($LASTEXITCODE -eq 0) {
    Log "all checks passed"
} else {
    Write-Host "`n[install] preflight reported $LASTEXITCODE problem(s) above - the app still opens, but fix them before scanning" -ForegroundColor Yellow
}

Log "done. Open TheRecon from the Desktop or Start Menu shortcut, or double-click TheRecon.bat"
