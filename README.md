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

## Chat Server

The chat app lives in `server/`. From the repo root, with the venv activated:

```bash
source venv/bin/activate
python server/server.py
```

This starts the API on `http://localhost:8000` and creates `data/database.db` on first run.

### Database Migrations

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/) (`server/alembic/`), not manual SQL. On every startup, `create_db_and_tables()` in `server/database/db.py` applies any pending migrations automatically — you don't need to run anything by hand to pick up a schema change made by someone else.

When *you* change a model in `server/database/models.py`, generate the migration for it:

```bash
source venv/bin/activate
alembic -c server/alembic.ini revision --autogenerate -m "describe the change"
```

Then open the generated file under `server/alembic/versions/` and check it did what you expect before committing it — autogenerate is a diff, so it can't tell a renamed column from a dropped-and-added one. The next `python server/server.py` (by you or anyone who pulls your change) will apply it automatically.

---

## Troubleshooting

See **[setup.md](setup.md)** for detailed setup instructions and a full troubleshooting section.
