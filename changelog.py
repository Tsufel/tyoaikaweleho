"""Release changelog — newest first. `python scripts/bump_version.py X.Y.Z` adds the
next entry; tests/test_release_hygiene.py checks it matches version.py."""

CHANGELOG: dict[str, list[str]] = {
    "2.1.9": [
        "Settings: new Round shift times (off by default). Shifts saved "
        "from the timer are rounded up, down or to the nearest 15, 30 or "
        "60 minutes. Shifts you type in yourself keep their exact times",
        "When a shift was rounded, the saved message says from what, and "
        "its Keep exact button (or Ctrl+Z) puts the exact times back",
    ],
    "2.1.8": [
        "Fixed: hidden medals in Achievements and Stats no longer show up "
        "as broken images",
        "Settings ▸ Your data has an Error log section: save a copy of it "
        "to send along when something goes wrong",
        "Timer: STOP is one bar again, centred under the clock. Right-click "
        "it (or press Shift+F10) to stop at an earlier time, or to change "
        "the start time or the job",
    ],
    "2.1.7": [
        "Fixed: Stats, the pet's details and Achievements open again after "
        "an update. Weleho no longer keeps an old copy of its screens",
        "Settings: the keyboard shortcut list is folded behind Show all",
        "Timer: the start time, job and week lines sit behind a ⋯ button",
    ],
    "2.1.6": [
        "Forgot to press STOP? Stop the shift at an earlier time, or fix "
        "its start time and job while it runs. A \"Still working?\" note "
        "shows up 2 hours past your daily target",
        "The Timer card shows how much you've worked this week, chips for "
        "your recent jobs and the time you'll reach your daily target",
        "Add a note to any shift, and undo an add or an edit from the toast",
        "Shifts list: duplicate a shift, copy it as text, filter the month "
        "(Ctrl+F) and use the new right-click menu",
        "Finnish public holidays are marked in the Shifts list, and they "
        "never break your streak",
        "Zoom the whole app with Ctrl + and Ctrl −, or reset it with Ctrl 0. "
        "Press Ctrl+K for a command palette, and ? or F1 for every shortcut",
        "Export any date range as CSV or as a simple workbook. The Full "
        "sheet now has a Notes column, and it can print your and your "
        "manager's names: turn on Settings ▸ Include names",
        "New Your data card in Settings: see your backups, make one now, "
        "and restore one safely (your current data is copied aside first)",
        "Safer data: a missing data file is restored from the newest "
        "backup, an import is saved in one go after a safety copy, and "
        "your files are copied aside before an update installs",
        "Achievements: more milestones, hidden calendar medals and a Hall "
        "of fame of your personal records. A recap of last week's hours "
        "shows up when a new week starts",
        "Stats: clearer axis labels, the change from the last period and "
        "a shifts donut",
        "The window title shows the running shift's time, so you can see "
        "it from the taskbar",
        "Fixed: the selected month in the month picker is highlighted "
        "again, and update checks now say why they failed",
    ],
    "2.1.4": [
        "New pet looks: Cosmic at level 5, Neon at 10, Gilded at 20 and "
        "Legend at 25. Pick one on the pet sheet once your pet gets there",
        "Now and then, after you end a shift, your pet shows up with a "
        "bazooka",
        "Shifts that overlap another one are flagged: saving asks first, "
        "and the Shifts list marks them with a warning sign",
        "Exporting in the first days of a month offers last month's "
        "timesheet, and Show in folder takes you straight to the saved file",
        "Picking a start time 6 hours or more in the past asks before the "
        "timer starts",
        "Safer data: a damaged data file is restored from the latest good "
        "backup automatically, and a file locked by another program is no "
        "longer mistaken for a damaged one",
        "Updates are only installed when their checksum matches",
        "Reduce effects now also calms the update progress bar, and the "
        "STOP button is easier to read",
    ],
    "2.1.2": [
        "Setting a past start time by clicking the dial no longer jumps "
        "about 8 hours back: clicking now steps back in small steps, just "
        "like the mouse wheel",
        "Stats has a new All time range, so shifts you entered by hand "
        "for earlier months show up too",
        "Rename or switch your pet in Settings ▸ Effects ▸ Pet; its "
        "sheet now has a Pet settings button that takes you there",
        "Right-clicking the pet opens its sheet more reliably, and the "
        "pet picture in the Timer card offer tells you how to get one",
    ],
    "2.1.1": [
        "Looking for the work pet? The Timer card now offers you one: pick "
        "a familiar or a wizard, or wave it off. You can switch, rename or "
        "turn it off any time in Settings ▸ Effects ▸ Pet",
        "Your achievements live on the Stats page: the trophy tile counts "
        "your medals, and the link under it shows every one and what's left "
        "to unlock",
    ],
    "2.1.0": [
        "Achievements: earn medals for your hours, streaks, early starts, "
        "late finishes and more. See them all from the new tile in Stats; "
        "anything you'd already earned is unlocked for you right away",
        "New achievements pop up with an animated card once you end your "
        "shift, so they never interrupt you mid-shift",
        "Work pet (Settings ▸ Effects ▸ Pet, off by default): a familiar or "
        "a wizard keeps you company on the Timer card. Give it a name, pet it "
        "with a click and open its sheet (right-click) to see its energy and "
        "level",
        "Your pet charges up as you log hours and levels up over time. It "
        "flies along while you work, gets tired towards the end of a shift "
        "and naps on your days off; it never goes hungry or sad",
        "Listen out for what it has to say, especially on Fridays",
    ],
    "2.0.1": [
        "Fixed \"Could not check for updates\" (certificate verify failed) on "
        "PCs where Windows was missing GitHub's security certificate; update "
        "checks, updates and DLC downloads now work there",
        "If a check or update still can't connect, an Open download page "
        "button takes you straight to the latest installer",
    ],
    "2.0.0": [
        "Brand-new glassy look: frosted-glass panels over an animated "
        "gradient background, smooth animations, light and dark themes",
        "Animated timer ring that glows and fills toward your daily target "
        "(set it in Settings), with rolling numbers and live earnings",
        "New Stats view: hours and earnings per day, week or month, shift "
        "breakdown, average per day and longest shift",
        "Start dial: forgot to clock in? Wind the idle clock back "
        "anticlockwise (drag, mouse wheel or ←/→) to start the shift earlier",
        "Liquid glass (Settings, off by default): an iPhone-style look with "
        "lenses that bend the background",
        "Lulz mode (Settings, off by default): your shift catches fire the "
        "longer it runs, flares up at milestones, burns blue in overtime "
        "and explodes when you clock out, with optional sound",
        "Reduce effects setting tones the animations down (also follows "
        "Windows' reduced-motion setting); animations pause when hidden",
        "Entries grouped by week with inline time editing and a new add/edit "
        "window with date and time pickers",
        "Image OCR results open in a new preview sheet; installing the OCR "
        "DLC no longer needs a restart. If you had it before, update it from "
        "Import ▸ From image or Settings ▸ DLC Store",
        "Updates now reopen the app automatically once they're installed",
        "Window position, size and maximised state are remembered and kept "
        "on-screen; starting the app again brings the open window forward",
        "All v1.3 rules carry over: crash recovery, close-while-running "
        "prompt, undo delete, keyboard shortcuts and safe saving",
    ],
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
