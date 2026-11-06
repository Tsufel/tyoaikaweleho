# Työaikaweleho v2.x — Timesheet day: names, shifts, export, restore (design plan)

> Status: **planning** — only *Restore from backup* is built so far.
> Release: **2.3**. Soft-depends on [V2_ACCURATE_PAY_PLAN.md](V2_ACCURATE_PAY_PLAN.md)
> (2.2: the export gains Break/Note columns there first).
> Listed in [BACKLOG.md](BACKLOG.md). Interacts with
> [V2_SYNC_PLAN.md](V2_SYNC_PLAN.md) (names and the shift list sync).
> Source: planning session, 2026-11-05.

## Why

Once a month everyone exports the EAS sheet and sends it to their manager.
That chore has rough edges today:

- **The EAS sheet has blank EMPLOYEE and MANAGER fields**
  (`excel_export._export_full` writes only the labels at A3/A5), so every
  sheet is filled in by hand in Excel.
- **The shift list can only grow.** Settings has *Add a shift*; renaming,
  hiding or reordering means editing `shifts.txt` in Notepad, and
  `storage.get_job_shift_list` re-adds every name ever used, so a deleted
  shift comes back. The default falls back to `"GPSR"`
  (`storage.get_default_job_shift`), which is no longer in the defaults, and
  the Excel import hard-codes it too (`import_excel.py`, two places).
- **Export is one month at a time, .xlsx only.** A year for a tax return or
  a quarter for a manager is twelve or three saves.
- **Backups exist but can't be used from the app.** `storage` keeps a `.bak`
  and 14 daily copies in `backups/`; restoring one means copying files by
  hand while the app is closed.

## Goals / non-goals

**Goals**
- The EAS sheet comes out ready to sign.
- Shifts can be renamed (optionally in past entries too), hidden and
  reordered in the app; hidden ones stay hidden.
- Export any date range, as .xlsx or CSV that Finnish Excel opens correctly.
- Restore a backup from Settings, safely.

**Non-goals**
- PDF export, emailing the sheet, signatures.
- Editing backups or merging two backups.
- Shift colours/icons (possible later on the same `job_shifts` list).

## Design

### Names on the EAS sheet

- Settings → *Timesheet* group (with export format and *include pay*, moved
  there): *Your name*, *Manager's name*.
- Stored top-level as `employee_name` and `manager_name`, cleaned like
  `pet_name` (trimmed, inner whitespace collapsed, control/bidi characters
  rejected), at most 60 characters, `""` = blank as today.
- `_export_full` writes them to B3 and B5, beside the existing labels.
  Nothing else in the EAS layout moves.

### Shift manager

- New top-level `job_shifts: [{"name": "Sales", "hidden": false}, …]` in
  display order — the list moves into `data.json`, as the sync plan already
  wants.
- **Migration on first read**: from `shifts.txt` (or `_DEFAULT_SHIFTS` if
  missing), in file order, all visible. Names used in entries but not in the
  file are **not** added any more.
- **Mirror for old versions**: every change rewrites `shifts.txt` as the
  visible list, so 2.2 and older still show the right shifts. A name found in
  `shifts.txt` but not in `job_shifts` (added by an older version) is
  appended on read.
- `get_job_shift_list()` returns visible names only. Pickers (timer
  combobox, `EntryModal`, OCR preview) also show the entry's current value
  when it is hidden or unknown, so editing an old entry never blanks it.
- **Rename** (confirm kind `rename_shift`): "Also rename it in N past
  entries?" — *Rename everywhere* (default) / *Only in the list* / *Cancel*.
  Rewrites `job_shift` on matching entries in one save.
- **Hide** ("Delete" in the UI): sets `hidden`; past entries untouched,
  Stats keeps showing them by name. *Show hidden* toggles them back.
- **Reorder**: drag handle; keyboard up/down buttons for accessibility.
- **Default shift**: `get_default_job_shift()` returns the stored value when
  it is visible, else the first visible shift, else `""`. No more `"GPSR"`
  fallback (this part ships early, in 2.1.4). `import_excel` uses
  `get_default_job_shift()` instead of its two hard-coded `"GPSR"`s, and the
  OCR DLC (`image_ocr._KNOWN_SHIFTS` / `_SHIFT_PAT`) matches against the
  user's list plus its built-in names.

### Export any range, and CSV

- New `export_range(start, end, kind)` beside `export_month` (same native
  save dialog; initial name `Hours 1.1.–31.12.2026.xlsx` / `.csv`):
  - `kind: "xlsx"` — Simple: one sheet, rows grouped by week as today.
    Full/EAS: one sheet per month (the employer's form is monthly), sheet
    names "Oct 2026".
  - `kind: "csv"` — columns
    `date;job_shift;time_in;time_out;break_minutes;hours;earnings;note`,
    `;` separator, decimal comma, UTF-8 with BOM, dates `YYYY-MM-DD` — so
    Excel with Finnish settings opens it into columns with no import wizard.
    Earnings only when *include pay* is on.
- The Export button opens a small sheet instead of the save dialog: presets
  *This month* (default, and what Ctrl+E keeps doing), *Last month*, *This
  year*, *Custom…*, and the format. `export_month` stays for compatibility
  and as the *This month* path.

### Restore from backup

Built: see V2_UI_API.md §5 *Your data* for the contract. In short:

- `list_backups()` lists only copies the app made (`data.json.bak`, daily
  `data-YYYY-MM-DD.json`, `manual-*`, `pre-import-*`, `pre-restore-*`,
  `pre-update-*/data.json`), newest first; `ok` = reads as app data through
  the normal loader.
- `restore_backup(name, confirm)` asks `restore_backup`, copies the current
  `data.json` to `backups/pre-restore-<YYYYmmdd-HHMMSS>.json` (an earlier
  draft said `data-before-restore-*`: that name starts with `data-` and
  would have looked like a daily snapshot to recovery; the daily pattern is
  now matched exactly, and pre-restore copies are never pruned), then swaps
  in the backup with `_save_raw` and emits `data:changed`. It is **not**
  refused while a shift runs: the running shift lives in `session.json` and
  is saved into the restored data when stopped.
- UI: Settings → *Your data* card: the data folder, backup count and last
  snapshot, *Back up now*, *Open data folder* and a list with *Restore*.

## Data model changes

- Top level: `employee_name`, `manager_name`, `job_shifts`.
- `shifts.txt` stays, as a mirror of the visible list.
- No entry changes.

## Migration

- `job_shifts` is built from `shifts.txt` on first read; names and the
  export keys default to `""`.
- **Downgrade table**

| Going back to | What happens |
|---|---|
| 2.2 / 2.1.4 | Works. Unknown top-level keys survive (`_load_raw` / `_save_raw` keep the whole dict). Shifts come from the mirrored `shifts.txt`; a shift added there shows up again in 2.3. Names are just not written to the sheet. |
| Restored backup older than 2.3 | Fine: missing keys are derived again on read. |

## Sync interaction

`employee_name`, `manager_name` and `job_shifts` are synced settings (whole
value, newer wins). Backups and restores are per machine. A restore on a
synced machine is an ordinary edit: the next sync pushes it, newer wins.

## Testing plan

- `tests/test_storage.py`: `job_shifts` migration, mirror both ways, hidden
  names not re-added from entries, default fallback; update the two tests
  that expect `"GPSR"` (`test_default_job_shift_default` in
  `test_storage.py`, `test_parse_dm_no_shift_default_is_gpsr_when_unconfigured`
  in `test_image_ocr.py`).
- `tests/test_excel_export.py`: names in B3/B5 and nothing else moved;
  multi-month Full export sheets; CSV bytes (BOM, `;`, decimal comma);
  `import_excel` reads a range export back.
- `tests/test_controller.py`: rename with and without past entries; restore
  refused while running; restore writes the before-restore copy and emits
  `data:changed`; `list_backups` on a broken file.
- `tests/test_api_contract.py`: new methods and confirm kinds.
- Frontend: shift manager (rename, hide, reorder by keyboard), export sheet
  presets, restore sheet.

## Implementation order

1. EAS names (smallest, most visible).
2. `job_shifts` + mirror + default fallback; shift manager UI.
3. `export_range` (xlsx, then CSV) and the export sheet.
4. Backups list and restore.
5. Release 2.3.

## Open questions (with the default we go with)

- *Rename in past entries by default?* — Yes; it's almost always a typo or a
  renamed team. The count is shown first.
- *CSV separator?* — `;` with decimal comma (Finnish Excel). A comma-separated
  option only if someone asks.
- *Does the employer want one file per month?* — Full/EAS stays one sheet per
  month inside one file; *This month* is unchanged.
