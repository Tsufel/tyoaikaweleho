# Työaikaweleho

<p align="center">
  <img src="splash.png" width="420" alt="Työvuoroweleho"/>
</p>

**Työaikaweleho** is a Windows desktop app for tracking shift work hours.
Start the timer when your shift begins, stop it when you finish — the app
logs every entry, calculates earnings, and exports a clean Excel timesheet
you can send straight to your employer.

<p align="center">
  <img src="toolbar.png" width="48" alt="icon"/>
  &nbsp;
  <a href="https://github.com/Tsufel/tyoaikaweleho/releases"><img alt="Download" src="https://img.shields.io/github/v/release/Tsufel/tyoaikaweleho?label=download&style=flat-square"></a>
  &nbsp;
  <img alt="Tests" src="https://github.com/Tsufel/tyoaikaweleho/actions/workflows/tests.yml/badge.svg">
</p>

---

## Features

- **Glassy UI** — frosted-glass panels, animated gradient background, light/dark themes
- **Animated timer ring** — fills toward your daily target with live hours and earnings; start now or at a chosen time
- **Stats** — hours and earnings per day, week or month, per-shift breakdown, averages
- **Lulz mode** *(off by default)* — your running shift catches fire
- **Crash recovery** — unfinished shifts survive app restarts and can be recovered with an edited end time
- **Manual entries** — add, edit, delete (with undo) or edit times inline; pick dates from a calendar
- **Excel export** — Simple layout (PVM / Start / End / Total) or full EAS format
- **Excel import** — bulk-import from existing timesheets
- **Image OCR** *(optional DLC)* — import entries from a photo or screenshot using Windows' built-in OCR
- **Per-user shift list** — customise your own `shifts.txt`; add new shifts directly in Settings
- **Auto-update** — notifies you when a new release is on GitHub and installs it silently; check on demand from Settings → Check for updates
- **No admin required** — installs to `%LOCALAPPDATA%`

---

## Installation

1. Go to the [**Releases**](https://github.com/Tsufel/tyoaikaweleho/releases) page
2. Download `TyoaikawelehoSetup_x.x.x.exe`
3. Run the installer — no administrator rights needed
4. Launch from the Start Menu shortcut

> **Uninstall:** via *Apps & features* → you'll be asked whether to keep or delete your timesheet data

---

## Running from source

**Requirements:** Python 3.12+, Node.js 22 (npm 10), Windows 10+ with the
WebView2 runtime (built into Windows 11 and current Windows 10).

```bash
git clone https://github.com/Tsufel/tyoaikaweleho.git
cd tyoaikaweleho
pip install -r requirements.txt
cd frontend && npm ci && npm run build && cd ..
python main.py
```

`run.bat` does the same (installs what is missing, builds the frontend once).

The UI is a Vite + Svelte 5 + TypeScript app in `frontend/`, hosted by
[pywebview](https://pywebview.flowrl.com/) (WebView2). `python main.py` loads
the built `frontend/dist`.

### Development workflow

```bash
cd frontend
npm run dev                 # Vite dev server on http://localhost:5173/
```

- **Against the real Python backend:** in a second terminal run
  `python main.py --dev` (or `--dev http://localhost:5174/` for another port).
  The window loads the dev server with hot reload and DevTools enabled.
- **Browser only:** open `http://localhost:5173/?mock` for a mock API with
  sample data, handy for design work.
- **Keep your real data safe:** set `WELEHO_DATA_DIR` to a scratch folder and
  the app reads/writes `data.json`, `shifts.txt`, `session.json`, backups and
  `error.log` there instead:

  ```powershell
  $env:WELEHO_DATA_DIR = "$env:TEMP\weleho-dev"; python main.py --dev
  ```

- `python main.py --smoke-test` starts hidden, waits for the UI to load and
  exits (0 on success); it always uses a temporary data folder unless
  `WELEHO_DATA_DIR` is set.

The Python ⇄ JS interface is documented in [`docs/V2_UI_API.md`](docs/V2_UI_API.md)
and mirrored in `frontend/src/lib/api/types.ts`; change both together.

---

## Project layout

```
main.py              entry point (--dev, --smoke-test)
version.py           app version + GitHub repo
storage.py           data.json persistence (atomic writes + .bak recovery)
timer.py             work timer + crash-recovery session file
utils.py             pure helpers (time parsing, app dir)
stats.py             hours/earnings summaries for the Stats view
excel_export.py      Excel export (Simple / Full layouts)
import_excel.py      Excel import
updater.py           auto-update check + verified installer download
webapp/
  app.py             pywebview window, close guard, theme, start-up
  api.py             js_api surface exposed to the frontend
  controller.py      all business flows (timer, entries, settings, ...)
  events.py          Python -> JS event pump
  win32.py           window placement, single instance, message boxes
services/
  dlc.py             secure DLC download / verify / install / remove
frontend/            Vite + Svelte 5 + TypeScript UI
  src/views/         timer, entries, stats, settings, OCR, modals
  src/fx/            gradient mesh, intro, Lulz fire
  src/lib/api/       typed bridge to webapp/api.py (+ mock for the browser)
  tests/             vitest suite
tests/               pytest suite (no display needed)
Tyoaikaweleho.spec   PyInstaller build definition
```

---

## Usage

### Timer

Pick the job/shift, then start now or at your default start time (or any
time from the picker). The ring fills toward your daily target and shows
elapsed time and earnings; stop to save the shift. Press **F5** to toggle
start/stop.

### Manual entries

Add a shift without the timer (**Ctrl+N**): type the date (e.g. `23.9.`) or
pick it from the calendar. Click any **Time In** / **Time Out** cell to edit it
inline; double-click a row, or press **Enter**/**F2** in the table, for the full
edit window. Deleting can be undone with **Ctrl+Z**.

### Stats

Choose a range and see hours and earnings per day, week or month, a per-shift
breakdown, average per day and your longest shift.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| F5 | Start / stop the timer |
| Ctrl+N | Add entry |
| Ctrl+E | Export to Excel |
| Ctrl+I | Import menu |
| Ctrl+Z | Undo delete |
| Ctrl+, | Settings |
| Ctrl+S / Esc | Save settings / back |
| PgUp / PgDn, Ctrl+← / → | Previous / next month |
| Ctrl+Home | Current month |

### Importing from Excel

Use **Import → From Excel…** (Ctrl+I) to load entries from a previous timesheet.
Both Simple (`date | time_in | time_out`) and EAS (`date | shift | time_in | time_out`) formats are detected automatically. Duplicates are skipped.

### Exporting to Excel

Click **Export** (Ctrl+E).
The format is set in **Settings → Output**:

| Format | Layout |
|--------|--------|
| **Simple** | PVM / Start / End / Total (h) — clean format for standard submissions |
| **Full** | EAS layout with employee/manager signature rows and pay calculations |

Optionally include a **Rate** and **Earned** section by ticking *Include total pay in export*.

### Settings

Settings open inside the main window (Ctrl+,). **Save** with Ctrl+S, go
back with Esc.

| Setting | Description |
|---------|-------------|
| Check for updates | Manually check GitHub for a newer app (and DLC) version |
| Default start time | Pre-fills the ⏰ button (e.g. `09:30`) |
| Pay rate (€/hr) | Used for the earnings display and optional export |
| Default job / shift | Applied automatically when the timer starts |
| Add new shift | Type a name and click **+ Add** to append it to your shift list |
| Edit shifts.txt → | Opens the shift file in Notepad for bulk editing |
| Output format | Simple or Full |
| Include total pay | Adds Rate + Earned rows to the Simple export |
| Appearance | System / Light / Dark theme |
| Daily target | Hours that fill the timer ring |
| Reduce effects | Tones animations down (also follows Windows' reduced motion) |
| Lulz | Fire effects around the running timer, off by default |

---

## Customising your shift list

Shift options are stored in `shifts.txt` next to the app (or next to `main.py` when running from source). One shift per line. The file is created automatically on first run with sensible defaults:

```
Sales
Support
Warehouse
Sales/Support
Training
Onboarding
```

You can add shifts directly in **Settings**, or open the file in Notepad from there for bulk editing. The file is gitignored so every user keeps their own personal list.

---

## Image OCR DLC *(optional)*

Allows importing shift entries from a photo or screenshot of a printed timesheet.

**To install:** open **Settings → DLC Store → ⬇ Install Image OCR**.
The app downloads `image_ocr.py` from the `dlc` branch and **Import → From image (OCR)…** becomes available straight away. Detected rows open in a preview sheet where you can fix and pick them before importing.

Uses **Windows built-in OCR** — no Tesseract, no admin rights, no extra download.
For best results with Finnish timesheets, ensure Finnish is added in
*Windows Settings → Time & Language → Language*.

If a newer DLC version is published, Settings → DLC Store shows a
**Update to vX.Y.Z** button. Clicking it re-downloads `image_ocr.py` and
reloads it.

DLC downloads are verified: the app checks the file's SHA-256 against the
hash published in `dlc_version.txt` and refuses mismatched downloads.

### Releasing a new DLC version (developers)

1. Bump `__version__` in `image_ocr.py`
2. Update `dlc_version.txt` to `<version> <sha256>` on one line, e.g.:
   ```bash
   python -c "import hashlib;print('1.2.0', hashlib.sha256(open('image_ocr.py','rb').read()).hexdigest())" > dlc_version.txt
   ```
3. Commit and push both files to the `dlc` branch:
   ```bash
   git checkout dlc
   git add image_ocr.py dlc_version.txt
   git commit -m "Bump Image OCR DLC to vX.Y.Z"
   git push origin dlc
   git checkout main
   ```

Existing users with the DLC installed see the update button on their next launch.

---

## Building the installer

**Prerequisites (developer machine only):**

| Tool | Notes |
|------|-------|
| Python 3.12+ | with pip |
| Node.js 22 | npm 10, for the frontend build |
| [Inno Setup 6](https://jrsoftware.org/isdl.php) | free, ~5 MB |

```batch
REM 1. Bump __version__ in version.py
REM 2. Run the build script
build.bat
REM → produces Output\TyoaikawelehoSetup_x.x.x.exe
```

The script automatically:
1. Installs the Python requirements and PyInstaller
2. Generates `icon.ico` from `toolbar.png`
3. Builds the frontend (`npm ci && npm run build` into `frontend/dist`)
4. Builds a one-directory bundle with `pyinstaller --noconfirm Tyoaikaweleho.spec`
5. Compiles the Inno Setup installer (which also installs the WebView2 runtime if missing)

To check a bundle without installing it: `dist\Tyoaikaweleho\Tyoaikaweleho.exe --smoke-test`.

**Releasing:**
1. Create a GitHub Release tagged `vx.x.x`
2. Attach `Output\TyoaikawelehoSetup_x.x.x.exe`
3. *(Recommended)* Also attach `TyoaikawelehoSetup_x.x.x.exe.sha256` containing the installer's SHA-256 hex digest:
   ```powershell
   (Get-FileHash Output\TyoaikawelehoSetup_x.x.x.exe -Algorithm SHA256).Hash.ToLower() | Out-File -Encoding ascii Output\TyoaikawelehoSetup_x.x.x.exe.sha256
   ```

Installed copies of the app detect the new release on next launch and offer to update silently. The updater only accepts release assets from this repository over HTTPS, and verifies the installer's SHA-256 when a `.sha256` asset is published.

---

## Running tests

```batch
pip install -r requirements-dev.txt
pytest tests/ -v

cd frontend
npm run check
npm test
```

The pytest suite covers storage (incl. atomic writes & corruption recovery), timer, the webapp controller and API contract, stats, updater URL/checksum validation, DLC verification, Excel import/export and time parsing; the vitest suite covers the frontend logic, stores and components.
Both run automatically on every push to `main` via GitHub Actions.

---

## Tech stack

| Layer | Library |
|-------|---------|
| Window | [pywebview](https://pywebview.flowrl.com/) (Edge WebView2) |
| UI | [Svelte 5](https://svelte.dev/) + TypeScript, built with [Vite](https://vite.dev/); charts with [d3-scale/d3-shape](https://d3js.org/) |
| Excel | [openpyxl](https://openpyxl.readthedocs.io/) |
| OCR | [winocr](https://pypi.org/project/winocr/) (Windows built-in) |
| Images | [Pillow](https://pillow.readthedocs.io/) |
| Packaging | [PyInstaller](https://pyinstaller.org/) + [Inno Setup 6](https://jrsoftware.org/isdl.php) |
| Tests | [pytest](https://pytest.org/), [Vitest](https://vitest.dev/) |

---

## License

MIT — see [LICENSE](LICENSE)
