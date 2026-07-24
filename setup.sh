#!/usr/bin/env bash
# setup.sh — Mac / Linux environment setup
# Usage: bash setup.sh
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
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓  $1${NC}"; }
fail() { echo -e "${RED}  ✗  $1${NC}"; }
info() { echo -e "${CYAN}  →  $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠  $1${NC}"; }
hr()   { echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

hr
echo -e "${BOLD}  Pune AI Builders Meetup — Environment Setup${NC}"
hr
echo ""

# ── Step 0: Correct directory ─────────────────────────────────────────────────
if [[ ! -f "requirements.txt" ]]; then
    fail "requirements.txt not found in the current directory."
    echo ""
    echo "  Please run this script from the repo root:"
    echo ""
    echo "    cd ai-cohort"
    echo "    bash setup.sh"
    echo ""
    exit 1
fi
ok "Running from correct directory"

# ── Step 1: Find Python 3.12+ (searches PATH + common install locations) ──────
echo ""
echo -e "${BOLD}  [1/7] Checking Python${NC}"

PYTHON=""
PYTHON_VERSION=""

find_python312() {
    # Build a list of candidate executables to probe:
    #   1. Names resolvable via PATH (command -v)
    #   2. Absolute paths in common install locations (even if not on PATH)
    local candidates=()

    # PATH-visible names — versioned first so we prefer the explicit match
    for name in python3.14 python3.13 python3.12 python3 python; do
        local resolved
        resolved=$(command -v "$name" 2>/dev/null) && candidates+=("$resolved")
    done

    # Common absolute locations that may not be on PATH
    local search_dirs=(
        # macOS Homebrew (Apple Silicon)
        /opt/homebrew/bin
        # macOS Homebrew (Intel)
        /usr/local/bin
        # macOS official installer framework
        /Library/Frameworks/Python.framework/Versions/3.12/bin
        /Library/Frameworks/Python.framework/Versions/3.13/bin
        /Library/Frameworks/Python.framework/Versions/3.14/bin
        # pyenv shims / versions
        "$HOME/.pyenv/shims"
        "$HOME/.pyenv/versions/3.12"*/bin
        "$HOME/.pyenv/versions/3.13"*/bin
        "$HOME/.pyenv/versions/3.14"*/bin
        # Conda / Miniforge / Mambaforge base envs
        "$HOME/anaconda3/bin"
        "$HOME/miniconda3/bin"
        "$HOME/mambaforge/bin"
        "$HOME/miniforge3/bin"
        # Linux system paths
        /usr/bin
        /usr/local/bin
    )

    for dir in "${search_dirs[@]}"; do
        # glob expansion for pyenv wildcard paths; skip if nothing matched
        [[ -d "$dir" ]] || continue
        for name in python3.14 python3.13 python3.12 python3 python; do
            local exe="$dir/$name"
            [[ -x "$exe" ]] && candidates+=("$exe")
        done
    done

    # De-duplicate while preserving order (compare resolved real paths)
    local seen=()
    local unique=()
    for exe in "${candidates[@]}"; do
        local real
        real=$(realpath "$exe" 2>/dev/null || echo "$exe")
        local already=0
        for s in "${seen[@]}"; do [[ "$s" == "$real" ]] && already=1 && break; done
        if [[ $already -eq 0 ]]; then
            seen+=("$real")
            unique+=("$exe")
        fi
    done

    for exe in "${unique[@]}"; do
        local raw
        raw=$("$exe" -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>/dev/null) || continue
        local major minor
        major=$(echo "$raw" | awk '{print $1}')
        minor=$(echo "$raw" | awk '{print $2}')
        if [[ "$major" -eq 3 && "$minor" -ge 12 ]]; then
            PYTHON="$exe"
            PYTHON_VERSION="$("$exe" --version 2>&1 | awk '{print $2}')"
            return 0
        fi
    done
    return 1
}

if find_python312; then
    ok "Found $PYTHON  ($PYTHON_VERSION)"
else
    warn "Python 3.12+ not found — attempting automatic install ..."
    echo ""

    OS="$(uname -s)"

    if [[ "$OS" == "Darwin" ]]; then
        # ── macOS: try Homebrew ───────────────────────────────────────────────
        if command -v brew &>/dev/null; then
            info "Running: brew install python@3.12"
            if brew install python@3.12; then
                # Homebrew installs to a versioned prefix; add it to PATH for this session
                BREW_PREFIX="$(brew --prefix python@3.12 2>/dev/null)/bin"
                export PATH="$BREW_PREFIX:$PATH"
                ok "Homebrew installed python@3.12"
            else
                fail "brew install python@3.12 failed."
                echo ""
                echo "  Try manually:  brew install python@3.12"
                echo "  Or download:   https://www.python.org/downloads/"
                echo ""
                exit 1
            fi
        else
            fail "Homebrew not found. Cannot auto-install Python on macOS."
            echo ""
            echo "  Install Homebrew first:  https://brew.sh"
            echo "  Then re-run this script."
            echo ""
            echo "  Or download Python 3.12 directly:  https://www.python.org/downloads/"
            echo ""
            exit 1
        fi

    elif [[ "$OS" == "Linux" ]]; then
        if command -v apt-get &>/dev/null; then
            # ── Debian / Ubuntu ───────────────────────────────────────────────
            info "Running: sudo apt-get install -y python3.12 python3.12-venv"
            if sudo apt-get install -y python3.12 python3.12-venv; then
                ok "apt installed python3.12"
            else
                # Try deadsnakes PPA as fallback
                info "Trying deadsnakes PPA ..."
                sudo apt-get install -y software-properties-common 2>/dev/null
                sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null
                sudo apt-get update -q
                if sudo apt-get install -y python3.12 python3.12-venv; then
                    ok "apt (deadsnakes) installed python3.12"
                else
                    fail "apt install python3.12 failed."
                    echo ""
                    echo "  Try manually:"
                    echo "    sudo add-apt-repository ppa:deadsnakes/ppa"
                    echo "    sudo apt update && sudo apt install python3.12 python3.12-venv"
                    echo ""
                    exit 1
                fi
            fi
        elif command -v dnf &>/dev/null; then
            # ── Fedora / RHEL ─────────────────────────────────────────────────
            info "Running: sudo dnf install -y python3.12"
            if sudo dnf install -y python3.12; then
                ok "dnf installed python3.12"
            else
                fail "dnf install python3.12 failed."
                echo ""
                echo "  Try manually:  sudo dnf install python3.12"
                echo ""
                exit 1
            fi
        else
            fail "Cannot auto-install Python: no supported package manager found (apt / dnf)."
            echo ""
            echo "  Install Python 3.12 manually for your distro, then re-run this script."
            echo ""
            exit 1
        fi

    else
        fail "Unsupported OS: $OS — cannot auto-install Python."
        echo ""
        echo "  Install Python 3.12 from https://www.python.org/downloads/ and re-run."
        echo ""
        exit 1
    fi

    # Re-check after install
    if find_python312; then
        ok "Using $PYTHON  ($PYTHON_VERSION)"
    else
        fail "Python 3.12+ still not found after install attempt."
        echo ""
        echo "  Close this terminal, open a new one, and re-run:  bash setup.sh"
        echo ""
        exit 1
    fi
fi

# ── Step 2: Virtual environment ───────────────────────────────────────────────
echo ""
echo -e "${BOLD}  [2/7] Virtual environment${NC}"

if [[ -d "venv" ]]; then
    # Check that the existing venv's Python is 3.12+ — if not, recreate it
    VENV_PYTHON="venv/bin/python"
    if [[ -x "$VENV_PYTHON" ]]; then
        venv_raw=$("$VENV_PYTHON" -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>/dev/null)
        venv_major=$(echo "$venv_raw" | awk '{print $1}')
        venv_minor=$(echo "$venv_raw" | awk '{print $2}')
        if [[ "$venv_major" -eq 3 && "$venv_minor" -ge 12 ]]; then
            ok "venv/ already exists and uses Python 3.$venv_minor — reusing it"
        else
            warn "venv/ exists but uses Python 3.$venv_minor (need 3.12+) — recreating it ..."
            rm -rf venv
            info "Creating venv/ with $PYTHON ..."
            if ! "$PYTHON" -m venv venv; then
                fail "Failed to create virtual environment."
                echo ""
                echo "  On Ubuntu/Debian you may need:  sudo apt install python3.12-venv"
                echo ""
                exit 1
            fi
            ok "venv/ recreated with Python $PYTHON_VERSION"
        fi
    else
        warn "venv/ exists but no python binary found inside — recreating it ..."
        rm -rf venv
        if ! "$PYTHON" -m venv venv; then
            fail "Failed to create virtual environment."
            echo ""
            exit 1
        fi
        ok "venv/ recreated with Python $PYTHON_VERSION"
    fi
else
    info "Creating venv/ ..."
    if ! "$PYTHON" -m venv venv; then
        fail "Failed to create virtual environment."
        echo ""
        echo "  On Ubuntu/Debian you may need to install the venv module first:"
        echo "    sudo apt install python3.12-venv  (or the matching version)"
        echo ""
        exit 1
    fi
    ok "venv/ created"
fi

# Activate
if ! source venv/bin/activate; then
    fail "Could not activate venv/bin/activate"
    echo ""
    echo "  Check that the venv was created correctly (venv/bin/python should exist)."
    echo ""
    exit 1
fi
ok "venv activated  ($(python --version))"

# ── Step 3: Install dependencies ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}  [3/7] Installing dependencies${NC}"

info "Upgrading pip ..."
if ! python -m pip install --upgrade pip --quiet 2>/dev/null; then
    warn "pip upgrade failed — continuing anyway"
fi

info "Installing from requirements.txt  (this can take 1–2 minutes on first run) ..."
if ! python -m pip install -r requirements.txt --quiet; then
    fail "Package installation failed."
    echo ""
    echo "  Try running it manually to see the error:"
    echo "    source venv/bin/activate"
    echo "    pip install -r requirements.txt"
    echo ""
    echo "  On a corporate network with SSL issues, try:"
    echo "    pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org"
    echo ""
    exit 1
fi
ok "All packages installed"

# ── Step 4: Register Jupyter kernel ───────────────────────────────────────────
echo ""
echo -e "${BOLD}  [4/7] Registering Jupyter kernel${NC}"

if python -m ipykernel install --user --name=meetup --display-name="AI Meetup (Python 3.12)" 2>/dev/null; then
    ok "Kernel 'AI Meetup (Python 3.12)' registered"
else
    warn "Kernel registration reported an issue — notebooks may still work"
fi

# ── Step 5: VS Code extensions ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  [5/7] VS Code extensions${NC}"

VSCODE_EXTENSIONS=("ms-toolsai.jupyter" "ms-python.python")

if command -v code &>/dev/null; then
    for ext in "${VSCODE_EXTENSIONS[@]}"; do
        # --install-extension is idempotent: exits 0 whether or not already installed
        if code --install-extension "$ext" --force 2>/dev/null 1>/dev/null; then
            ok "VS Code extension: $ext"
        else
            warn "Could not auto-install $ext"
            echo "     Install manually: VS Code → Extensions (Cmd+Shift+X) → search '$ext'"
        fi
    done
else
    warn "VS Code 'code' command not found in PATH — skipping extension install"
    echo ""
    echo "  If VS Code is installed, enable the CLI tool first:"
    echo "    VS Code → Command Palette (Cmd+Shift+P) → 'Shell Command: Install code in PATH'"
    echo "    Then re-run:  bash setup.sh"
    echo ""
    echo "  Or install the two required extensions manually:"
    echo "    Open VS Code → Extensions (Cmd+Shift+X) → search and install:"
    echo "      • Jupyter     (publisher: Microsoft)  — ms-toolsai.jupyter"
    echo "      • Python      (publisher: Microsoft)  — ms-python.python"
fi

# ── Step 6: Verify imports ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  [6/7] Verifying packages${NC}"

IMPORT_ERRORS=0

check_import() {
    local label="$1"
    local module="${2:-$1}"
    local version
    version=$(python -c "
import $module
try:
    from importlib.metadata import version as _v
    print(_v('$label'))
except Exception:
    v = getattr($module, '__version__', 'ok')
    print(v)
" 2>/dev/null)
    if [[ $? -eq 0 ]]; then
        ok "$label  ($version)"
    else
        fail "$label — import failed"
        IMPORT_ERRORS=$((IMPORT_ERRORS + 1))
    fi
}

check_import "openai"
check_import "jupyter" "jupyter_core"
check_import "ipykernel"
check_import "pandas"
check_import "requests"
check_import "notebook"

if [[ $IMPORT_ERRORS -gt 0 ]]; then
    echo ""
    fail "$IMPORT_ERRORS package(s) could not be imported."
    echo ""
    echo "  Try:"
    echo "    source venv/bin/activate"
    echo "    pip install -r requirements.txt"
    echo ""
    exit 1
fi

# ── Step 7: Execute verification notebook ────────────────────────────────────
echo ""
echo -e "${BOLD}  [7/7] Running notebooks/test_setup.ipynb${NC}"
info "Executing notebook — this takes about 10 seconds ..."

TMPOUT=$(mktemp /tmp/test_setup_out_XXXXXX.ipynb)
TMPERR=$(mktemp /tmp/test_setup_err_XXXXXX.txt)

jupyter nbconvert \
    --to notebook \
    --execute \
    --ExecutePreprocessor.timeout=60 \
    --ExecutePreprocessor.kernel_name=meetup \
    --output "$TMPOUT" \
    notebooks/test_setup.ipynb 2>"$TMPERR"

NB_EXIT=$?

if [[ $NB_EXIT -eq 0 ]]; then
    ok "All notebook cells executed successfully"
    rm -f "$TMPOUT" "$TMPERR"
else
    fail "Notebook execution failed — a cell raised an error"
    echo ""
    if [[ -s "$TMPERR" ]]; then
        echo -e "${RED}  ── Error output ─────────────────────────────────────${NC}"
        # Strip the nbconvert progress lines, keep the actual traceback
        grep -v "^\[NbConvertApp\] Converting\|^\[NbConvertApp\] Executing\|^\[NbConvertApp\] Writing" \
            "$TMPERR" | head -40 | while IFS= read -r line; do
            echo "    $line"
        done
        echo ""
    fi
    rm -f "$TMPOUT" "$TMPERR"
    echo "  Fix the issue above, then re-run the notebook from terminal:"
    echo ""
    echo "    source venv/bin/activate"
    echo "    jupyter nbconvert --to notebook --execute \\"
    echo "      --ExecutePreprocessor.kernel_name=meetup \\"
    echo "      --output /tmp/test_out.ipynb \\"
    echo "      notebooks/test_setup.ipynb"
    echo ""
    exit 1
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
hr
echo -e "${GREEN}${BOLD}  Setup complete! Your environment is ready.${NC}"
hr
echo ""
echo "  ── Open notebooks in VS Code ───────────────────────────"
echo "  Launch VS Code FROM THIS TERMINAL (not from Spotlight/Dock):"
echo ""
echo "    code ."
echo ""
echo "  Then:"
echo "    1. Open  notebooks/test_setup.ipynb"
echo "    2. Kernel selector (top-right) → AI Meetup (Python 3.12)"
echo "    3. Run cells with Shift+Enter"
echo ""
echo "  ── Open notebooks in browser ───────────────────────────"
echo ""
echo "    source venv/bin/activate"
echo "    jupyter notebook notebooks/"
echo ""
