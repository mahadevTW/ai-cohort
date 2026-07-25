# setup.ps1 — Windows PowerShell environment setup
# Usage: powershell -ExecutionPolicy Bypass -File setup.ps1
#
# What it does:
#   1. Verifies you are in the right directory
#   2. Finds Python 3.12+
#   3. Creates a virtual environment (skips if it already exists)
#   4. Installs all dependencies from requirements.txt
#   5. Registers the Jupyter kernel
#   6. Installs VS Code extensions (skips if VS Code is not in PATH)
#   7. Verifies all package imports
#   8. Executes notebooks/test_setup.ipynb end-to-end on the terminal

# ── Colour helpers ────────────────────────────────────────────────────────────
function ok($msg)   { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function err($msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function info($msg) { Write-Host "  [-->]  $msg" -ForegroundColor Cyan }
function warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function hr()       { Write-Host ("=" * 52) -ForegroundColor DarkGray }

hr
Write-Host "  Pune AI Builders Meetup -- Environment Setup" -ForegroundColor White
hr
Write-Host ""

# ── Step 0: Correct directory ─────────────────────────────────────────────────
if (-not (Test-Path "requirements.txt")) {
    err "requirements.txt not found in the current directory."
    Write-Host ""
    Write-Host "  Please run this script from the repo root:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    cd ai-cohort"
    Write-Host "    powershell -ExecutionPolicy Bypass -File setup.ps1"
    Write-Host ""
    exit 1
}
ok "Running from correct directory"

# ── Step 1: Find Python 3.12+ ─────────────────────────────────────────────────
Write-Host ""
Write-Host "  [1/7] Checking Python" -ForegroundColor White

$PYTHON = $null
$PYTHON_VERSION = $null

function Test-PythonExe($exe) {
    # Returns $true and sets $script:PYTHON / $script:PYTHON_VERSION if exe is 3.12+
    try {
        $out = & $exe -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $false }
        $parts = $out.Trim().Split(" ")
        if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 12) {
            $script:PYTHON = $exe
            $script:PYTHON_VERSION = (& $exe --version 2>&1).ToString().Trim()
            return $true
        }
    } catch {}
    return $false
}

function Find-Python312 {
    # 1. Windows Python Launcher (py.exe) — most reliable on Windows
    if (Get-Command "py" -ErrorAction SilentlyContinue) {
        foreach ($ver in @("3.14", "3.13", "3.12")) {
            $out = & py "-$ver" -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) {
                $parts = $out.Trim().Split(" ")
                if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 12) {
                    $script:PYTHON = "py -$ver"
                    $script:PYTHON_VERSION = (& py "-$ver" --version 2>&1).ToString().Trim()
                    return $true
                }
            }
        }
    }

    # 2. PATH-visible command names
    foreach ($cmd in @("python3.14", "python3.13", "python3.12", "python3", "python")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            if (Test-PythonExe $cmd) { return $true }
        }
    }

    # 3. Common absolute install paths (not always on PATH)
    $searchRoots = @(
        # Windows Store / official installer (per-user)
        "$env:LOCALAPPDATA\Programs\Python",
        # System-wide official installer
        "C:\Python312", "C:\Python313", "C:\Python314",
        "C:\Program Files\Python312",
        "C:\Program Files\Python313",
        "C:\Program Files\Python314",
        # Conda / Miniforge / Mambaforge
        "$env:USERPROFILE\anaconda3",
        "$env:USERPROFILE\miniconda3",
        "$env:USERPROFILE\mambaforge",
        "$env:USERPROFILE\miniforge3",
        "$env:ProgramData\miniconda3",
        "$env:ProgramData\anaconda3",
        # winget default install location
        "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    )

    foreach ($root in $searchRoots) {
        if (-not (Test-Path $root)) { continue }
        # Handle versioned subdirs like LOCALAPPDATA\Programs\Python\Python312\
        $subdirs = Get-ChildItem -Path $root -Directory -ErrorAction SilentlyContinue |
                   Where-Object { $_.Name -match "Python3(12|13|14)" } |
                   Sort-Object Name -Descending
        foreach ($sub in $subdirs) {
            $exe = Join-Path $sub.FullName "python.exe"
            if ((Test-Path $exe) -and (Test-PythonExe $exe)) { return $true }
        }
        # Also check python.exe / python3.exe directly in root
        foreach ($name in @("python3.12.exe","python3.13.exe","python3.14.exe","python.exe")) {
            $exe = Join-Path $root $name
            if ((Test-Path $exe) -and (Test-PythonExe $exe)) { return $true }
        }
    }

    return $false
}

if (Find-Python312) {
    ok "Found $PYTHON  ($PYTHON_VERSION)"
} else {
    warn "Python 3.12+ not found — attempting automatic install via winget ..."
    Write-Host ""

    $wingetAvailable = Get-Command "winget" -ErrorAction SilentlyContinue
    if ($wingetAvailable) {
        info "Running: winget install Python.Python.3.12 --silent"
        winget install --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -eq 0) {
            ok "winget installed Python 3.12"
            # Refresh PATH for this session so the new install is visible
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH","User")
        } else {
            warn "winget install reported a non-zero exit — checking if Python 3.12 is now available anyway ..."
        }
    } else {
        warn "winget not available — cannot auto-install."
        Write-Host ""
        Write-Host "  Install Python 3.12 manually:" -ForegroundColor Yellow
        Write-Host "    https://www.python.org/downloads/"
        Write-Host "    Check 'Add Python to PATH' during installation."
        Write-Host "    Then close this terminal, open a new one, and re-run setup.ps1."
        Write-Host ""
        exit 1
    }

    # Re-search after install (winget may have added to PATH or a known location)
    if (Find-Python312) {
        ok "Using $PYTHON  ($PYTHON_VERSION)"
    } else {
        err "Python 3.12+ still not found after install attempt."
        Write-Host ""
        Write-Host "  Close this terminal, open a new one, and re-run:" -ForegroundColor Yellow
        Write-Host "    powershell -ExecutionPolicy Bypass -File setup.ps1"
        Write-Host ""
        exit 1
    }
}

# ── Step 2: Virtual environment ───────────────────────────────────────────────
Write-Host ""
Write-Host "  [2/7] Virtual environment" -ForegroundColor White

function New-Venv {
    info "Creating venv\ ..."
    if ($PYTHON -like "py *") {
        $pyver = $PYTHON.Split(" ")[1]
        & py $pyver -m venv venv
    } else {
        & $PYTHON -m venv venv
    }
    if ($LASTEXITCODE -ne 0) {
        err "Failed to create virtual environment."
        Write-Host ""
        Write-Host "  Make sure Python is properly installed and try again." -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
}

if (Test-Path "venv") {
    $venvPython = "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $venvRaw = & $venvPython -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
        $venvParts = $venvRaw.Trim().Split(" ")
        $venvMinor = [int]$venvParts[1]
        if ([int]$venvParts[0] -eq 3 -and $venvMinor -ge 12) {
            ok "venv\ already exists and uses Python 3.$venvMinor -- reusing it"
        } else {
            warn "venv\ exists but uses Python 3.$venvMinor (need 3.12+) -- recreating it ..."
            Remove-Item -Recurse -Force venv
            New-Venv
            ok "venv\ recreated with $PYTHON_VERSION"
        }
    } else {
        warn "venv\ exists but no python.exe found inside -- recreating it ..."
        Remove-Item -Recurse -Force venv
        New-Venv
        ok "venv\ recreated with $PYTHON_VERSION"
    }
} else {
    New-Venv
    ok "venv\ created"
}

# Activate
$activateScript = "venv\Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    err "Activation script not found: $activateScript"
    Write-Host ""
    Write-Host "  The venv may be corrupted. Delete it and re-run:" -ForegroundColor Yellow
    Write-Host "    Remove-Item -Recurse -Force venv"
    Write-Host "    powershell -ExecutionPolicy Bypass -File setup.ps1"
    Write-Host ""
    exit 1
}

try {
    & $activateScript
} catch {
    err "Could not activate the virtual environment."
    Write-Host ""
    Write-Host "  If you see an execution policy error, run:" -ForegroundColor Yellow
    Write-Host "    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
    Write-Host "  Then re-run setup.ps1"
    Write-Host ""
    exit 1
}

$activated_version = (python --version 2>&1).ToString().Trim()
ok "venv activated  ($activated_version)"

# ── Step 3: Install dependencies ──────────────────────────────────────────────
Write-Host ""
Write-Host "  [3/7] Installing dependencies" -ForegroundColor White

info "Upgrading pip ..."
python -m pip install --upgrade pip --quiet 2>$null

info "Installing from requirements.txt  (this can take 1-2 minutes on first run) ..."
python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    err "Package installation failed."
    Write-Host ""
    Write-Host "  Try running it manually to see the full error:" -ForegroundColor Yellow
    Write-Host "    venv\Scripts\Activate.ps1"
    Write-Host "    pip install -r requirements.txt"
    Write-Host ""
    Write-Host "  On a corporate network with SSL issues, try:" -ForegroundColor Yellow
    Write-Host "    pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org"
    Write-Host ""
    exit 1
}
ok "All packages installed"

# ── Step 4: Register Jupyter kernel ───────────────────────────────────────────
Write-Host ""
Write-Host "  [4/7] Registering Jupyter kernel" -ForegroundColor White

python -m ipykernel install --user --name=meetup --display-name="AI Meetup ($PYTHON_VERSION)" 2>$null
if ($LASTEXITCODE -eq 0) {
    ok "Kernel 'ai-cohort ($PYTHON_VERSION)' registered"
} else {
    warn "Kernel registration reported an issue -- notebooks may still work"
    warn "If the kernel is missing later, run:"
    Write-Host "    python -m ipykernel install --user --name=meetup --display-name=`"AI Meetup ($PYTHON_VERSION)`""
}

# ── Step 5: VS Code extensions ────────────────────────────────────────────────
Write-Host ""
Write-Host "  [5/7] VS Code extensions" -ForegroundColor White

$vscodeExtensions = @("ms-toolsai.jupyter", "ms-python.python")

if (Get-Command "code" -ErrorAction SilentlyContinue) {
    foreach ($ext in $vscodeExtensions) {
        # --install-extension is idempotent: exits 0 whether or not already installed
        & code --install-extension $ext --force 2>$null 1>$null
        if ($LASTEXITCODE -eq 0) {
            ok "VS Code extension: $ext"
        } else {
            warn "Could not auto-install $ext"
            Write-Host "     Install manually: VS Code -> Extensions (Ctrl+Shift+X) -> search '$ext'"
        }
    }
} else {
    warn "VS Code 'code' command not found in PATH -- skipping extension install"
    Write-Host ""
    Write-Host "  Install the two required extensions manually:" -ForegroundColor Yellow
    Write-Host "    Open VS Code -> Extensions (Ctrl+Shift+X) -> search and install:"
    Write-Host "      Jupyter  (publisher: Microsoft)  -- ms-toolsai.jupyter"
    Write-Host "      Python   (publisher: Microsoft)  -- ms-python.python"
}

# ── Step 6: Verify imports ────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [6/7] Verifying packages" -ForegroundColor White

$importErrors = 0

function Check-Import {
    param($label, $module = $null)
    if (-not $module) { $module = $label }
    $script = @"
import $module
try:
    from importlib.metadata import version as _v
    print(_v('$label'))
except Exception:
    print(getattr($module, '__version__', 'ok'))
"@
    $result = python -c $script 2>$null
    if ($LASTEXITCODE -eq 0 -and $result) {
        ok "$label  ($($result.Trim()))"
    } else {
        err "$label -- import failed"
        $script:importErrors++
    }
}

Check-Import "openai"
Check-Import "jupyter" "jupyter_core"
Check-Import "ipykernel"
Check-Import "pandas"
Check-Import "requests"
Check-Import "notebook"

if ($importErrors -gt 0) {
    Write-Host ""
    err "$importErrors package(s) could not be imported."
    Write-Host ""
    Write-Host "  Try:" -ForegroundColor Yellow
    Write-Host "    venv\Scripts\Activate.ps1"
    Write-Host "    pip install -r requirements.txt"
    Write-Host ""
    exit 1
}

# ── Step 7: Execute verification notebook ─────────────────────────────────────
Write-Host ""
Write-Host "  [7/7] Running notebooks/test_setup.ipynb" -ForegroundColor White
info "Executing notebook -- this takes about 10 seconds ..."

$tmpOut = [System.IO.Path]::GetTempFileName() + ".ipynb"
$tmpErr = [System.IO.Path]::GetTempFileName()

jupyter nbconvert `
    --to notebook `
    --execute `
    "--ExecutePreprocessor.timeout=60" `
    "--ExecutePreprocessor.kernel_name=meetup" `
    --output $tmpOut `
    notebooks/test_setup.ipynb 2>$tmpErr

$nbExit = $LASTEXITCODE

if ($nbExit -eq 0) {
    ok "All notebook cells executed successfully"
} else {
    err "Notebook execution failed -- a cell raised an error"
    Write-Host ""
    if (Test-Path $tmpErr) {
        Write-Host "  -- Error output -----------------------------------" -ForegroundColor Red
        # Strip nbconvert progress lines, show the actual traceback
        Get-Content $tmpErr |
            Where-Object { $_ -notmatch "^\[NbConvertApp\] Converting|^\[NbConvertApp\] Executing|^\[NbConvertApp\] Writing" } |
            Select-Object -First 40 |
            ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        Write-Host ""
    }
    Write-Host "  Fix the issue above, then re-run the notebook from terminal:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    venv\Scripts\Activate.ps1"
    Write-Host "    jupyter nbconvert --to notebook --execute ``"
    Write-Host "      --ExecutePreprocessor.kernel_name=meetup ``"
    Write-Host "      --output `$env:TEMP\test_out.ipynb ``"
    Write-Host "      notebooks\test_setup.ipynb"
    Write-Host ""
}

if (Test-Path $tmpOut) { Remove-Item $tmpOut -ErrorAction SilentlyContinue }
if (Test-Path $tmpErr) { Remove-Item $tmpErr -ErrorAction SilentlyContinue }

if ($nbExit -ne 0) { exit 1 }

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
hr
Write-Host "  Setup complete! Your environment is ready." -ForegroundColor Green
hr
Write-Host ""
Write-Host "  -- Open notebooks in VS Code ------------------------"
Write-Host "  Launch VS Code FROM THIS TERMINAL:"
Write-Host ""
Write-Host "    code ."
Write-Host ""
Write-Host "  Then:"
Write-Host "    1. Open  notebooks\01_what_makes_software_intelligent.ipynb"
Write-Host "    2. Kernel selector (top-right) -> AI Meetup (Python 3.12)"
Write-Host "    3. Run cells with Shift+Enter"
Write-Host ""
Write-Host "  -- Open notebooks in browser ------------------------"
Write-Host ""
Write-Host "    venv\Scripts\Activate.ps1"
Write-Host "    jupyter notebook notebooks\"
Write-Host ""
