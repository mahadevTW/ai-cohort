# Setup Guide — Pune AI Builders Meetup

Follow this guide to get your laptop ready before the session. Budget **10–15 minutes**.

---

## Step 1 — Choose your OS

### Mac or Linux → run `setup.sh`

```bash
git clone https://github.com/mahadevTW/ai-cohort
cd ai-cohort
bash setup.sh
```

### Windows → run `setup.ps1`

Open **PowerShell** (search "PowerShell" in Start — not Command Prompt):

```powershell
git clone https://github.com/mahadevTW/ai-cohort
cd ai-cohort
powershell -ExecutionPolicy Bypass -File setup.ps1
```

> **PowerShell execution policy error?** Run this once, then retry:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

## What the script does

The script runs 7 steps and logs `[OK]` for each one:

| Step | What it does |
|---|---|
| 1 | Finds Python 3.12+ on your machine |
| 2 | Creates a virtual environment (`venv/`) |
| 3 | Installs all packages from `requirements.txt` |
| 4 | Registers the ** (Python 3.12)** Jupyter kernel |
| 5 | Installs the **Jupyter** and **Python** VS Code extensions |
| 6 | Imports every required package and prints its version |
| 7 | Executes `notebooks/test_setup.ipynb` end-to-end in the terminal |

If all 7 steps show `[OK]`, your machine is ready. Jump to [Opening Notebooks](#opening-notebooks).

---

## Python not installed?

The script will tell you if Python 3.12+ is missing. Install it first, then re-run the script.

**Mac (Homebrew — recommended):**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.12
```

**Mac (direct installer):** [python.org/downloads](https://www.python.org/downloads/)

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install python3.12 python3.12-venv
```

**Fedora / RHEL:**
```bash
sudo dnf install python3.12
```

**Windows:** Download from [python.org/downloads](https://www.python.org/downloads/).
During installation **check "Add Python to PATH"**, then restart PowerShell.

---

## VS Code not installed?

Download from [code.visualstudio.com](https://code.visualstudio.com/).

The setup script installs the required extensions automatically if `code` is in your PATH.
On Mac, if `code` is not found, run this once inside VS Code:

```
Command Palette (Cmd+Shift+P) → Shell Command: Install 'code' command in PATH
```

Then re-run `bash setup.sh` — it will pick up the extensions step.

If you skip this, install the two extensions manually:
- `Jupyter` by Microsoft (`ms-toolsai.jupyter`)
- `Python` by Microsoft (`ms-python.python`)

---

## Opening Notebooks

### VS Code (recommended)

> **Mac/Linux:** Always launch VS Code from the terminal with `code .`, never from Spotlight or Dock. This ensures the correct Python environment is inherited.

```bash
# Mac / Linux
code .
```
```powershell
# Windows
code .
```

Inside VS Code:
1. Open `notebooks/test_setup.ipynb`
2. Kernel selector (top-right corner) → **(Python 3.12)**
3. Run All (`Shift+Enter` cell by cell, or the ▶▶ button)

### Browser

```bash
# Mac / Linux
source venv/bin/activate
jupyter notebook notebooks/
```
```powershell
# Windows
venv\Scripts\Activate.ps1
jupyter notebook notebooks\
```

Opens at `http://localhost:8888`. Select **(Python 3.12)** from the Kernel menu.

---

## Troubleshooting

**`python3.12: command not found` on Mac**
Homebrew puts Python in `/opt/homebrew/bin/`. Add it to your PATH:
```bash
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Wrong kernel / `ModuleNotFoundError` in notebook**
Click the kernel name (top-right in VS Code, or Kernel menu in Jupyter) and switch to **(Python 3.12)**.
If it is not listed, run this from inside the repo directory:
```bash
source venv/bin/activate   # Mac/Linux
python -m ipykernel install --user --name=meetup --display-name="ai-cohort (Python 3.12)"
```
```powershell
venv\Scripts\Activate.ps1  # Windows
python -m ipykernel install --user --name=meetup --display-name="ai-cohort (Python 3.12)"
```

**`pip install` fails — SSL error (corporate network)**
```bash
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

**`venv\Scripts\Activate.ps1` not found on Windows**
You are in the wrong directory. Make sure you are inside `ai-cohort\`.

**Packages install but notebook still shows import errors**
The notebook is on the wrong kernel. Select **(Python 3.12)** and restart the kernel (`Kernel → Restart`).

**Step 7 fails — notebook execution error**
The terminal output shows which cell failed and the exact Python traceback.
Fix the issue shown, then re-run from terminal:
```bash
source venv/bin/activate
jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.kernel_name=meetup \
  --output /tmp/test_out.ipynb \
  notebooks/test_setup.ipynb
```
```powershell
venv\Scripts\Activate.ps1
jupyter nbconvert --to notebook --execute `
  --ExecutePreprocessor.kernel_name=meetup `
  --output $env:TEMP\test_out.ipynb `
  notebooks\test_setup.ipynb
```
