"""Release changelog — update this alongside version.py when cutting a release."""

CHANGELOG: dict[str, list[str]] = {
    "1.3.0": [
        "Dark mode: choose System, Light or Dark in Settings; the table, "
        "message boxes and popups follow it",
        "Keyboard shortcuts: Ctrl+N add, Ctrl+E export, Ctrl+I import, "
        "Ctrl+←/→ months (full list in Settings)",
        "Undo delete: bring back a deleted shift from the status line, "
        "or with Ctrl+Z, for 8 seconds",
        "A locked data.json no longer loses work: shifts, edits and dialog "
        "input are kept so you can retry",
        "Daily backups: data.json is copied to a backups folder once a day "
        "(the 14 most recent are kept)",
        "Crash recovery: new Recover shift window with an editable end time; "
        "closing it now resumes the shift",
        "Timer: pick the job/shift before START, F5 asks before stopping, "
        "and a ▾ button opens the time picker",
        "Start times later than now count as yesterday (for overnight "
        "shifts); if only a little ahead, you're asked first",
        "Shifts over 14 hours ask before saving; a timer stopped within a "
        "minute is not saved as an entry",
        "Inline time edits: invalid times are flagged instead of silently "
        "dropped; click straight to the next cell",
        "Add entry uses your Settings defaults (Time Out = start + 8 h), "
        "shows the duration live and accepts dates like 23.9.",
        "Settings: Save (Ctrl+S) is always visible at the top, and going "
        "Back (or Esc) with unsaved changes asks to save them",
        "Excel export: totals calculate on open, unfinished shifts show "
        "'In progress', clearer error messages",
        "Window size and position are remembered; dialogs open centred over "
        "the app and stay on-screen",
        "One 'Import ▾' menu replaces the separate import buttons; "
        "Edit/Delete grey out when no row is selected",
        "The app icon and start-up splash now show in the installed app",
        "Unexpected errors are shown and written to error.log instead of "
        "vanishing",
        "Fixes: updates no longer freeze the window, weeks sort right across "
        "New Year, odd saved dates show again",
    ],
    "1.2.2": [
        "Reliability fix: prevent duplicate running instances, which could "
        "cause update installs to fail with a file-access error",
    ],
    "1.2.1": [
        "Right-click the start button to pick a custom shift start time",
    ],
    "1.2.0": [
        "Overnight shift support: shifts spanning midnight now calculate correctly",
        "Time Out column shows '+1' indicator for overnight shifts",
        "Excel export: overnight shifts export correctly (=End-Start stays positive)",
        "Bare-hour time input: type '9' or '13' anywhere a time is entered",
        "Changelog popup: shows what's new on first launch after each update",
    ],
    "1.1.0": [
        "OCR engine switched to Windows built-in (winocr) — no Tesseract needed",
        "D.M. date format support for OCR import (e.g. 'Monday 4.5. 10-16')",
        "Remove Image OCR button added to Settings → DLC Store",
        "Image OCR DLC update notifications in Settings",
        "GitHub Actions updated to Node 24",
    ],
    "1.0.0": [
        "Initial release",
    ],
}
