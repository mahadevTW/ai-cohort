# Rebind Rise — AI Engineering cohort

---

## One-Time Setup

Run the setup script for your OS. It installs everything and verifies your environment end-to-end.

### Mac / Linux

```bash
git clone https://github.com/mahadevTW/ai-cohort
cd ai-cohort
bash setup.sh
```

### Windows

Open **PowerShell** (not Command Prompt):

```powershell
git clone https://github.com/mahadevTW/ai-cohort
cd ai-cohort
powershell -ExecutionPolicy Bypass -File setup.ps1
```

> If PowerShell blocks the script, run this once first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> Then re-run `setup.ps1`.

The script will:
- Find or prompt you to install Python 3.12+
- Create a virtual environment
- Install all dependencies
- Register the (Python 3.12)** Jupyter kernel
- Install the required VS Code extensions
- Execute `notebooks/test_setup.ipynb` in the terminal to confirm everything works

If all steps show `[OK]`, you are ready.

## Opening Notebooks

### VS Code (recommended)

Launch VS Code **from the same terminal** where you ran the setup script:

**Mac / Linux**
```bash
source venv/bin/activate
code .
```

**Windows**
```powershell
venv\Scripts\Activate.ps1
code .
```

> **Windows webview error?** If VS Code shows `Error loading webview: Could not register service worker: InvalidStateError`, close VS Code and relaunch with:
> ```bash
> code . --disable-gpu
> ```

Then:
1. Open any notebook under `notebooks/`
2. Click the kernel selector in the **top-right corner**
3. Choose **(Python 3.12)**
4. Run cells with `Shift+Enter`

### Browser

```bash
source venv/bin/activate   # Mac / Linux
jupyter notebook notebooks/
```
```powershell
venv\Scripts\Activate.ps1  # Windows
jupyter notebook notebooks\
```

---

## Notebooks

| # | Notebook | Topic |
|---|---|---|
| — | `test_setup.ipynb` | Verify your environment (run this first) |
---

## Troubleshooting

See **[setup.md](setup.md)** for detailed setup instructions and a full troubleshooting section.
