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

- **One-click timer** — START NOW or START AT a predefined time (e.g. 09:30)
- **Crash recovery** — unfinished shifts survive app restarts; auto-closes at 8 h
- **Manual entries** — add, edit, or delete any shift entry; pick the date from a 📅 popup calendar
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

**Requirements:** Python 3.12+, Windows 10+

```bash
git clone https://github.com/Tsufel/tyoaikaweleho.git
cd tyoaikaweleho
pip install -r requirements.txt
python main.py
```

---

## Project layout

```
main.py              entry point
version.py           app version + GitHub repo
storage.py           data.json persistence (atomic writes + .bak recovery)
timer.py             work timer + crash-recovery session file
utils.py             pure helpers (time parsing, app dir)
excel_export.py      Excel export (Simple / Full layouts)
import_excel.py      Excel import
updater.py           auto-update check + verified installer download
ui/
  theme.py           colors, fonts, table style
  dialogs.py         month picker, add/edit entry dialogs
  calendar_popup.py  clickable month-grid date picker
  settings_view.py   in-window settings + update check + DLC store
  timer_panel.py     timer card (start/stop, elapsed, earnings)
  entries_table.py   monthly table with week totals + inline editing
  main_window.py     App window composing everything
services/
  dlc.py             secure DLC download / verify / install / remove
tests/               pytest suite (no display needed)
```

---

## Usage

### Timer

| Button | Action |
|--------|--------|
| **▶ START NOW** | Starts the timer at the current time |
| **⏰ 09:30** | Starts the timer backdated to your default start time |
| **⏹ STOP SHIFT** | Stops and saves the shift |

Press **F5** to toggle start/stop from anywhere in the app.

### Manual entries

Click **+ Add entry manually** to log a shift without the timer — type the
date or click 📅 to pick it from a calendar.
Click any **Time In** or **Time Out** cell in the table to edit it inline.
Double-click a row (or use **✏ Edit**) for the full edit dialog.

### Importing from Excel

Click **Import from Excel…** to load entries from a previous timesheet.
Both Simple (`date | time_in | time_out`) and EAS (`date | shift | time_in | time_out`) formats are detected automatically. Duplicates are skipped.

### Exporting to Excel

Click **Export to Excel →** at the bottom of the window.
The format is set in **Settings → Output**:

| Format | Layout |
|--------|--------|
| **Simple** | PVM / Start / End / Total (h) — clean format for standard submissions |
| **Full** | EAS layout with employee/manager signature rows and pay calculations |

Optionally include a **Rate** and **Earned** section by ticking *Include total pay in export*.

### Settings (⚙)

Settings open inside the main window — use **← Back** to return.

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

You can add shifts directly in **Settings → + Add**, or open the file with **Edit shifts.txt →**. The file is gitignored so every user keeps their own personal list.

---

## Image OCR DLC *(optional)*

Allows importing shift entries from a photo or screenshot of a printed timesheet.

**To install:** open **Settings → DLC Store → ⬇ Install Image OCR**.
The app downloads `image_ocr.py` from the `dlc` branch. Restart the app and a purple **📷 Import from Image…** button will appear in the top bar.

Uses **Windows built-in OCR** — no Tesseract, no admin rights, no extra download.
For best results with Finnish timesheets, ensure Finnish is added in
*Windows Settings → Time & Language → Language*.

If a newer DLC version is published, Settings → DLC Store shows a
**🔄 Update to vX.Y.Z** button. Clicking it re-downloads `image_ocr.py`;
restart the app to pick up the change.

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
| [Inno Setup 6](https://jrsoftware.org/isdl.php) | free, ~5 MB |

```batch
REM 1. Bump __version__ in version.py
REM 2. Run the build script
build.bat
REM → produces Output\TyoaikawelehoSetup_x.x.x.exe
```

The script automatically:
1. Installs PyInstaller, winocr, Pillow
2. Generates `icon.ico` from `toolbar.png`
3. Builds a one-directory bundle with PyInstaller (bundling all dependencies)
4. Compiles the Inno Setup installer

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
```

162 tests covering storage (incl. atomic writes & corruption recovery), timer, updater URL/checksum validation, DLC verification, Excel import/export, and time parsing.
Tests run automatically on every push to `main` via GitHub Actions.

---

## Tech stack

| Layer | Library |
|-------|---------|
| UI | [customtkinter](https://github.com/TomSchimansky/CustomTkinter) |
| Excel | [openpyxl](https://openpyxl.readthedocs.io/) |
| OCR | [winocr](https://pypi.org/project/winocr/) (Windows built-in) |
| Images | [Pillow](https://pillow.readthedocs.io/) |
| Packaging | [PyInstaller](https://pyinstaller.org/) + [Inno Setup 6](https://jrsoftware.org/isdl.php) |
| Tests | [pytest](https://pytest.org/) |

---

## License

MIT — see [LICENSE](LICENSE)
