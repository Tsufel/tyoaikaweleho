# Improvement ideas (open)

These ideas from the go-crazy sweep (`docs/IMPROVEMENT_PLAN.md`, catalogue #1–#126) have not shipped yet.
Each one was checked against the code on `feat/go-crazy-improvements` (Nov 2026).
The numbers match the catalogue.
File:line references were correct when this was written, but they will drift.

Two ideas that were thought to be open turned out to be done already:
- **#9** puts elapsed time in the window title (`webapp/app.py` `title_for` / `title_loop`).
- **#121** shows a weekly recap toast (`frontend/src/views/recap/`).

Sizes: **S** is under an hour, **M** is a few hours, **L** is a day or more or needs design.

## Quick wins (S)

| # | Idea | Status | What's left |
|---|------|--------|-------------|
| 16 | Remove dead `WorkTimer` helpers | open | Nothing calls `elapsed_str`, `elapsed_seconds` or `start_time_str` (timer.py:79-90, 100-103). Only five tests use them (tests/test_timer.py:68-92). Delete the helpers and those tests, and drop any import this leaves unused. |
| 27 | Delete/restore toast grammar | open | The toast reads "Deleted on Tue 23 Sep, 09:00–17:00." Change it to "Deleted the shift on …". Make the same change for Restored and Could not restore in EntriesView.svelte:346/502/507, controller.py:1031/1065 and the messages in mock.ts. |
| 33 | Misleading editor test name | open | The test at frontend/tests/entries.test.ts:136 is named "allows clearing time out", but the code doesn't allow it. Rename the test. Alternatively, change the code to allow clearing time out. |
| 60 | Topbar during boot failure/loading | open | The view picker, month nav, settings and their shortcuts all stay active while `phase !== 'ready'`. The error card offers only "Try again". Hide those controls, guard the commands, and add "Open data folder" and "Copy details" to the error card. |
| 76 | Close the window when the frontend never answers | partial | A hung renderer is already handled. If `close:requested` gets delivered but nothing answers it, the window can't be closed. Fix: a second X more than ~10 s later forces the close. Add tests for `on_closing` (there are none today). |
| 79 | DLC: refuse install without a checksum | open | `services/dlc.py` installs unverified code when `dlc_version.txt` lists no hash. The app updater refuses in that case. Make the DLC refuse too: fetch the hash before downloading, and drop the `verified=False` path (backend, types, mock, settings message). |
| 80 | Two-digit years ("2.6.26") | open | Change both regexes, utils.py:24 and frontend/src/lib/time.ts:87, to accept `\d{2}` and read it as 20yy. Add tests on both sides, and check that the OCR and import callers still read dates correctly. |
| 83 | Mock `get_stats` parity | open | The mock differs from `stats.py` in three ways. It treats an entry as open only when time_out is missing, where stats.py checks both times. It has no tie-break for the longest shift. It has no secondary sort by name in by_shift. Fix all three in mock.ts and add vitest cases. |
| 95 | Stats / pet_stats test gaps | partial | The test for the longest-shift tie-break passes trivially. Nothing covers the by_shift name tie-break, a missing time_in, pay_rate 0, the W53/W01 week boundary, or an overnight shift on the last day. There are no direct `pet_stats` tests of the window edges (today-55, today-56, today, tomorrow). |
| 110 | run.bat / build.bat hygiene | open | Reinstall deps when requirements.txt changes, using a hash stamp. Add a `dev.bat` that runs with a scratch `WELEHO_DATA_DIR`. Have build.bat write the installer `.sha256`, like CI does. Stop build.bat from regenerating the tracked `icon.ico` on every build. |

## Medium (M)

| # | Idea | Status | What's left |
|---|------|--------|-------------|
| 40 | "Undo import" on the import result | open | The import already makes a pre-import backup, but the result alert has no undo. Return the added ids and fingerprints, and add a one-save `undo_import` that skips entries edited since the import. The result toast gets an Undo action. |
| 49 | "Exporter" achievement + pet reaction on export | open | The app records no export events, has no export achievement, and the pet doesn't react to exports. Best done together with #96, which adds the event counter. |
| 94 | Pet work anniversary (työvuosipäivä) | open | Add `first_shift_date` to `get_pet_stats` as an additive key, plus a pure `anniversaryYears()` that handles Feb 29. Show a pet greeting at most once a day, with the hat and confetti. Update the API doc §10.2 and add tests on both sides. |
| 111 | Source runs: the DLC UI overwrites the tracked `image_ocr.py` | open | On a source run, `dlc_path()` points at the repo copy, so install and remove rewrite or delete source code. Either refuse on source runs or send it to `WELEHO_DATA_DIR/dlc`, and load it via `spec_from_file_location`. |
| 126 | Seasonal touches | partial | The Konami egg and the generic holiday greeting are done. Still to do: a `seasons.ts` (Christmas snow, Vappu, Juhannus accents), season-specific greeting lines, a `ui_prefs.seasonal` opt-out, and respecting reduced motion. |

## Large (L)

| # | Idea | Status | What's left |
|---|------|--------|-------------|
| 17 | Pause / break button | blocked | This depends on the 2.2 break model (`break_min` per entry, see docs/V2_ACCURATE_PAY_PLAN.md). Then it needs a PAUSED timer state, pause intervals saved in session.json, pause and resume API calls, a button, and the break folded into the saved entry. Add crash-recovery tests. |
| 32 | Multi-select + bulk delete with one undo | open | Today only one row can be selected. This needs a selection set (Ctrl/Shift+click, Shift+arrows, Ctrl+A), a selection bar, a one-save `delete_entries` / `restore_entries` on the backend, and one toast "Deleted N shifts" with Undo. |
| 96 | Tool achievements via an add-only event counter | open | Add an add-only `events` key in data.json ({name: {count, first_on}}) with a sanitising reader and merge-on-write. Bump it on export, OCR and import. Add the first_export, first_ocr and first_import achievements. This is the only idea that touches stored data, so it needs storage robustness tests. It unblocks #49. |

## Suggested order

1. Batch the S items into one PR, mostly small and test-only: #16, #27, #33, #83, #95, then #80, #60, #76 and #79.
2. #111 and #110, the developer-safety items.
3. #40 (undo import), then #32 (bulk delete), which needs a delete-many helper like #40's.
4. #96, then #49 on top of it, and #94 and #126 as fun follow-ups.
5. #17 after the 2.2 break model.
