# Työaikaweleho v2 — Python ⇄ JS API contract

Source of truth for the interface between `webapp/api.py` (exposed to the page
as `window.pywebview.api`) and the Svelte frontend. The TypeScript mirror is
`frontend/src/lib/api/types.ts`; **change both together**.

Behavioural reference: the v1.3 customtkinter `ui/` package, removed from the
tree at the 2.0.0 cutover and kept on branch `legacy-ctk` (tag `v1.3.0`).
Every rule there is preserved; where this document names a `ui/…` function,
the new flow must behave the same.

---

## 1. Conventions

- **Calling.** pywebview maps JS arguments positionally onto the Python
  method. Every method below lists its positional parameters; trailing
  optional ones may be omitted (`undefined` → Python default). Calls return a
  Promise. JS must wait for the `pywebviewready` window event before the first
  call (`lib/api/index.ts` handles this; in a plain browser it uses
  `lib/api/mock.ts`).
- **Threads.** js_api calls run on pywebview worker threads. The controller
  holds one `RLock` around every storage/timer/session access, so calls are
  serialised; a slow call (file dialog, network) never holds the lock while
  waiting on the user or the network.
- **Never throws.** Every method is wrapped by `@_guarded`: an unexpected
  exception is written to `error.log` (`storage.append_error_log`) and
  returned as `{ok:false, status:'error', error:{code:'internal', …}}`.
  The frontend shows "Something went wrong … Your saved shifts are not
  affected. The details were written to: {error_log}" (one box at a time).
- **Dates/times.** Dates are ISO `YYYY-MM-DD`; clock times are `HH:MM` (24 h);
  datetimes are local-naive ISO `YYYY-MM-DDTHH:MM:SS`; `*_epoch_ms` are Unix
  ms. Durations are integer **minutes** unless the name says otherwise.
  Money is a float in € (`earnings`); format in JS as `€{x.toFixed(2)}`.
- **Display strings** that v1.3 produced with `strftime` (`display_date`,
  month `label`, confirm messages) are produced by Python in English so the
  wording stays identical.

## 2. Result envelope

Every mutating / flow method returns:

```ts
{ ok: boolean, status: Status, message?: string, ...payload }
```

| status | ok | meaning |
|---|---|---|
| `ok` | true | done (generic success / read) |
| `saved` | true | an entry or settings were written |
| `discarded` | true | a running shift was dropped on purpose (too short or user chose discard) |
| `cancelled` | true | user backed out (file dialog closed, chose Cancel/Keep running); nothing changed |
| `needs_confirm` | false | Python needs an answer — see `confirm` |
| `invalid` | false | input rejected; `field` + `message` say what (nothing written) |
| `error` | false | could not complete; `error:{code,message,detail?}`; state is unchanged unless the flow says otherwise |

`message` is a short user-facing note for the status line/toast when present
(e.g. `"Shift under a minute — not saved"`). `error` results also repeat
`error.message` as the top-level `message`.

### Error codes
`save_failed` (OSError writing data.json — locked/AV/etc.), `not_found`,
`recovery_pending`, `already_running`, `not_running`, `stale`
(confirm token no longer matches), `file_locked` (export target open in
Excel), `dlc_unavailable`, `dlc_failed`, `network`, `not_frozen`
(update from source), `update_failed`, `ocr_failed`, `internal`.

## 3. Confirm protocol (blocking modals → async)

When a flow needs a decision, Python returns

```ts
{ ok:false, status:'needs_confirm', confirm: ConfirmRequest }
ConfirmRequest = { kind, title, message, options:[{id,label,variant?}],
                   default, cancel, icon:'question'|'warning', token?, details? }
```

The frontend shows a glass modal (generic `ConfirmModal`, or a renderer
registered for that `kind`), then **re-calls the same method with the same
arguments plus `confirm` = the list of all answers so far**, appending
`{kind, choice, token?}` (choice = one of `options[].id`). Escape / closing the
modal answers with `cancel`. Answers accumulate: a chain such as
`over_24h → discard_shift` is re-called with both answers. Python processes the
answers it recognises and ignores the rest; if a `token` no longer matches
current state (e.g. a different shift is now running) it returns
`error/stale` and the frontend re-reads state.

`lib/api/flow.ts` (foundation) provides `runFlow(call)` which loops
`needs_confirm` → `confirm()` → re-call and resolves with the final result.

### Confirm kinds

| kind | asked by | options (id) | default / cancel |
|---|---|---|---|
| `stop_shift` | `timer_stop` source `shortcut` (F5) | `stop` "Yes", `keep` "No" | `stop` / `keep`; icon warning when >14 h |
| `long_shift` | `timer_stop` source `button`, elapsed >14 h and <24 h | `stop`, `keep` | `stop` / `keep` |
| `over_24h` | `timer_stop` any source, elapsed ≥24 h | `save` "Save until HH:MM", `discard` (danger), `keep` "Keep running" | `keep` / `keep` |
| `discard_shift` | after `over_24h=discard`; `recovery_resolve('discard')`; `timer_discard` | `discard` (danger), `cancel` | `cancel` / `cancel` |
| `start_ahead` | `timer_start` mode `at`, picked time 0–6 h ahead of now | `now` "Start now (HH:MM)", `earlier` "From yesterday/today HH:MM", `cancel` | `now` / `cancel` |
| `long_entry` | `save_entry`, `update_entry_field` when result >14 h | `save` "Save anyway", `cancel` | `save` / `cancel` |
| `delete_entry` | `delete_entry` | `delete` (danger), `cancel` | `cancel` / `cancel` |
| `close_running` | `close_app` while a shift runs | `stop_close` "Stop, save & close", `close` "Close anyway", `cancel` "Stay open" | `stop_close` / `cancel` |
| `remove_dlc` | `dlc_remove` | `remove` (danger), `cancel` | `cancel` / `cancel` |

Messages are the v1.3 texts (see `ui/timer_panel.py`, `ui/dialogs.py`,
`ui/main_window.py`). `details` carries machine values for custom renderers:
`{start_iso, elapsed_minutes, capped_end?, time_in?, time_out?, overnight?}`.

## 4. Running-shift data safety (invariants)

The current shift must never be lost:

1. `timer_start` writes `session.json` **before** returning `ok`.
2. `session.json` is removed only after the entry is safely in data.json, or
   after an explicit discard (too-short, `discard` choices).
3. A failed save (`save_failed`) restarts the timer with the **same start and
   job** and leaves `session.json`; result is `error/save_failed`, the timer
   payload shows it running, and the user can press STOP again.
4. "Close anyway" leaves `session.json`; next launch offers recovery.
5. While recovery is pending, `timer_start` returns `error/recovery_pending`;
   recovery is re-offered until saved, resumed or discarded (a failed save
   keeps it pending).
6. `install_update` saves window placement first; the session file is left
   alone (it is recovered after the update relaunch).
7. All writes go through `storage._save_raw` (atomic + `.bak` + daily
   snapshot). `WELEHO_DATA_DIR`, when set, redirects data.json, shifts.txt,
   error.log, backups and session.json (dev/test/smoke runs).

## 5. Methods

`R<X>` = envelope plus fields `X`. `T` = `TimerState`, `E` = `EntryRow`.

### App / lifecycle
| method | params | returns |
|---|---|---|
| `bootstrap()` | — | `R<{data: Bootstrap}>` (§7). Also records `last_seen_version` (after computing `changelog`). |
| `frontend_ready()` | — | `R<{}>`. Shows the hidden window (restores placement/maximised). Watchdog shows it anyway after 6 s. |
| `set_close_guard(enabled)` | `boolean` | `R<{}>`. `true` once the page handles `close:requested`; while `false` the native close just closes (session stays → recovery). |
| `close_app(confirm?)` | `ConfirmAnswer[]` | see §6.8. On success the window is destroyed (Promise may never resolve). |
| `set_theme(appearance, dark)` | `'System'\|'Light'\|'Dark'`, `boolean` (effective) | `R<{}>`. Live preview: native title-bar dark mode/caption colour only; persisted only via `save_settings`. |
| `log_client_error(message, stack?)` | `string`, `string` | `R<{}>`. Appends to error.log. |
| `open_shifts_file()` | — | `R<{}>`. `os.startfile(shifts.txt)` (creates it with defaults first). |

### Timer
| method | params | returns |
|---|---|---|
| `get_timer()` | — | `R<{timer: T}>` |
| `timer_start(mode, time?, job_shift?, confirm?)` | `'now'\|'at'`, `HH:MM` (for `at`), `string`, answers | `R<{timer: T}>` status `ok` / `cancelled` / `needs_confirm(start_ahead)` / `error(already_running\|recovery_pending)` / `invalid(field:'time')` |
| `timer_stop(source, confirm?)` | `'button'\|'shortcut'\|'close'`, answers | `R<{timer: T, entry?: E}>` §6.1 |
| `timer_discard(confirm?)` | answers | `R<{timer: T}>` needs `discard_shift`; → `discarded` |
| `recovery_resolve(action, end?, confirm?)` | `'resume'\|'save'\|'discard'`, `HH:MM`, answers | `R<{timer: T, entry?: E, recovery: Recovery\|null}>` §6.3 |

### Entries
| method | params | returns |
|---|---|---|
| `list_month(year, month)` | ints (month 1–12) | `R<{data: MonthData}>` (§9) |
| `save_entry(draft, confirm?)` | `EntryDraft` (id absent = add), answers | `R<{entry: E}>` §6.5 |
| `update_entry_field(id, field, value, confirm?)` | `string`, `'time_in'\|'time_out'`, raw text, answers | `R<{entry?: E, unchanged?: true}>` §6.4 |
| `delete_entry(id, confirm?)` | `string`, answers | `R<{deleted: WorkEntry, description: string}>` §6.6 |
| `restore_entry(entry)` | `WorkEntry` (from `deleted`) | `R<{entry: E}>` status `saved` / `error(save_failed)` |
| `get_entry(id)` | `string` | `R<{entry: E}>` / `error(not_found)` |

### Shifts & settings
| method | params | returns |
|---|---|---|
| `get_settings()` | — | `R<{settings: Settings, shifts: string[]}>` |
| `save_settings(draft)` | `SettingsDraft` | `R<{settings: Settings, shifts: string[]}>` §6.9 |
| `add_job_shift(name)` | `string` | `R<{added: boolean, shifts: string[]}>`; `added:false` + message `"'X' is already in the shift list."` when present (case-insensitive); `invalid` when blank |
| `save_ui_prefs(prefs)` | `Partial<UiPrefs>` | `R<{settings: Settings}>` — instant toggles (Lulz/Lulz sound/Reduce effects/Liquid glass) that do not go through the Settings Save button |

### Stats
| method | params | returns |
|---|---|---|
| `get_stats(start_iso, end_iso, granularity)` | dates inclusive, `'day'\|'week'\|'month'` | `R<{data: StatsData}>` (§10) / `invalid(field:'range')` when end < start or > 3700 days |

### Import / export / OCR
| method | params | returns |
|---|---|---|
| `export_month(year, month)` | ints | Native save dialog (initial `Hours {Month YYYY}.xlsx`, `.xlsx`). `cancelled` / `saved{path}` / `error(file_locked\|internal)` with v1.3 messages. Uses stored format / include-pay / pay rate. |
| `import_excel()` | — | Native multi-open dialog (`*.xlsx *.xls`). `cancelled` / `ok{imported, skipped, files, errors: string[]}` |
| `ocr_pick_and_extract()` | — | Native multi-open dialog (images). `cancelled` / `error(dlc_unavailable)` / `error(ocr_failed, errors)` when nothing extracted and errors / `ok{candidates: OcrCandidate[], errors}` (empty `candidates` → "No entries found") |
| `ocr_save(rows)` | `OcrRow[]` (checked rows only, trimmed) | `R<{imported, skipped, invalid_skipped}>` status `saved` / `error(save_failed)`. Rows missing date or time_in are skipped and counted in `invalid_skipped` (v1.3 "Rows skipped" warning). |

### Updates & DLC
| method | params | returns |
|---|---|---|
| `check_updates()` | — | Manual check. `ok{app: {current, latest, available}, dlc: {current, latest, available}\|null}` / `error(network)`. If an app update is found Python also remembers its URLs and emits `update:available`. |
| `open_download_page()` | — | Opens the GitHub releases page (fixed URL from `version.GITHUB_REPO`) in the default browser: the manual way out when a check or update fails. `ok` / `error(internal)`. |
| `install_update()` | — | Uses the URLs Python remembered (JS never passes URLs). `error(not_frozen)` from source; otherwise emits `update:installing`, downloads/verifies off-lock; on success the installer closes the app (Promise never resolves); on failure `error(update_failed, message)`. |
| `get_dlc_status()` | — | `R<{dlc: DlcStatus}>` |
| `dlc_install()` | — | Blocks until done. `ok{verified, dlc}` (module reloaded without restart when compatible) / `error(dlc_failed, message)`. Emits `dlc:status`. |
| `dlc_remove(confirm?)` | answers | `needs_confirm(remove_dlc)` → `ok{dlc}` / `error(dlc_failed)`. Emits `dlc:status`. |

## 6. Flows

### 6.1 Timer stop — `timer_stop(source, confirm)`
Order of checks (port of `TimerPanel.stop` / `toggle`):

1. Not running → `ok` (nothing to do).
2. `source==='shortcut'` and no `stop_shift` answer → `needs_confirm(stop_shift)`
   ("Stop the shift started at HH:MM (Xh YYm ago) and save it?"; icon warning
   if >14 h). `keep` → `cancelled`. `stop` → continue **without** step 5.
3. Elapsed < 60 s → stop, clear session → `discarded`, message
   `"Shift under a minute — not saved"`.
4. Elapsed ≥ 24 h → `needs_confirm(over_24h)` (capped end = start + 8 h,
   `details.capped_end`).
   - `keep` → `cancelled`.
   - `discard` → `needs_confirm(discard_shift)`; `discard` → clear session →
     `discarded`, message `"Shift discarded"`; `cancel` → `cancelled`.
   - `save` → time_out = capped end; go to 6.
5. `source==='button'` and elapsed > 14 h → `needs_confirm(long_shift)`;
   `keep` → `cancelled`. (`close` and confirmed `shortcut` skip this.)
6. Stop, build entry, `storage.save_entry`.
   - OSError → restart timer with same start/job (session kept) →
     `error(save_failed)` with message "The shift could not be saved and is
     still running. … Close any program that may be locking data.json and
     press STOP again." `timer.running === true`.
   - OK → clear session → `saved{entry, timer}`. Frontend switches to the
     entry's month and selects it.

`token` for 1–5 = running `start_iso`.

### 6.2 Timer start — `timer_start(mode, time, job_shift, confirm)`
- Running → `error(already_running)`; recovery pending → `error(recovery_pending)`.
- `job_shift` = given ‖ default job; blank → `"—"`.
- `mode:'now'` → start now → `ok{timer}`.
- `mode:'at'`: `time` parsed with `parse_time_input` (invalid → `invalid`).
  If `start_time_needs_confirm` is false → start at `resolve_start_time` → `ok`.
  Otherwise `needs_confirm(start_ahead)` ("It's HH:MM now, so the next T is
  still ahead. Start the shift now, or from T yesterday/today (Ddd DD Mon)?").
  `now` → start now; `earlier` → start at resolved time; `cancel` → `cancelled`.
  `now` is evaluated at re-call time.

The start buttons: "START NOW" (`now`), "⏰ {default_start_time}" (`at` default),
"▾" / right-click opens the time picker then `at` with the picked time.

### 6.3 Crash recovery
`bootstrap().data.recovery` is non-null when `session.json` holds a valid
session (an invalid one is cleared silently). It carries `start_iso`,
`job_shift`, `elapsed_minutes`, `over_limit` (≥8 h), `suggested_end`
(start+8 h when over limit, else now). The frontend shows `RecoverShiftModal`
**after** the changelog modal; START is blocked until resolved.

- `resume` (also Esc / closing the modal) → timer runs from the saved start;
  `ok{timer, recovery:null}`; frontend jumps to the start's month.
- `save` with `end` → invalid end → `invalid(field:'end')` ("End time must be a
  valid time (e.g. 17:00)."). OSError → `error(save_failed)` and
  `recovery` returned again with `suggested_end = end` (modal stays). OK →
  clear session → `saved{entry, recovery:null}`; frontend shows the entry.
- `discard` → `needs_confirm(discard_shift)` → `discarded{recovery:null}`.

### 6.4 Inline edit — `update_entry_field(id, field, value, confirm)`
JS owns the editor (Enter = strict, Tab/blur/click elsewhere/scroll = lenient,
Esc = revert, ` +1` suffix stripped, red state cleared once the text parses,
Alt+Tab keeps the editor open). Python:
- `value` parses to the stored value → `ok{unchanged:true}`.
- Unparseable → `invalid(field)`. JS: strict → keep open, red, select all;
  lenient → close, revert, status `"Invalid time, not saved"` (only if the
  text differs from the original).
- Entry gone → `error(not_found)` (JS just closes the editor).
- Both times set and > 14 h → `needs_confirm(long_entry)`
  ("09:00–23:30 is 14h 30m (ending the next day). Save it anyway?");
  `cancel` → `cancelled` and JS **reopens the editor with the typed text**.
- OSError → `error(save_failed)`; JS shows the error and reopens the editor
  with the typed text (original kept for the unchanged check).
- OK → `saved{entry}`; JS refreshes the month, keeping selection/scroll.

Leaving the month, opening Settings/Add/Edit/Delete/Export/month picker and
closing the app first commit an open edit; if that does not succeed the action
is abandoned (`editGuard.commitEdits()` → `false`).

### 6.5 Entry add/edit — `save_entry(draft, confirm)`
Draft fields are raw text. Validation order and messages as `EditEntryDialog._save`:
`invalid(date)` "Enter the date as YYYY-MM-DD or D.M.YYYY (e.g. 2026-09-23 or
23.9.2026).", `invalid(time_in)` "Time In must be a valid time (e.g. 09:30).",
`invalid(time_out)` "Time Out must be a valid time (e.g. 17:00)." (empty
time_out allowed). >14 h → `needs_confirm(long_entry)`. OSError →
`error(save_failed)` — modal stays open with everything typed. OK →
`saved{entry}`; modal closes, view jumps to the entry's month and selects it.
New-entry defaults (date = today if viewing the current month, else the 1st of
the viewed month; job = default job; time in = default start; time out =
+8 h) and the live duration line ("Duration: 8h 00m (+1 day) — unusually
long", "No time out yet — the shift counts as 0h") are computed in JS
(`lib/time.ts`).

### 6.6 Delete + undo
`delete_entry(id)` → `needs_confirm(delete_entry)` ("Delete the shift on Tue 23
Sep, 09:00–17:00?") → `ok{deleted, description}` / `error(save_failed)` /
`error(not_found)`. JS refreshes and shows a toast `"Deleted {description}."`
with **Undo** for 8 s; Ctrl+Z triggers it only while the toast is visible and
no modal is open. Undo → `restore_entry(deleted)` → `saved` (jump + select,
toast `"Restored {description}."`) or `error(save_failed)` → toast
`"Could not restore {description}."` with **Retry** (same entry kept).

### 6.7 Changelog
`bootstrap().data.changelog` is the list of versions newer than
`last_seen_version` (null on first install or same version), newest first.
Shown once, before recovery.

### 6.8 Close
Native close → Python `closing` handler cancels it and emits
`close:requested` (when the close guard is on). JS:
1. If a modal is open: restore/focus the window and that modal; stop.
2. `editGuard.commitEdits()`; false → stop.
3. `runFlow(api.close_app)`:
   - Not running → placement saved, window destroyed.
   - Running → `needs_confirm(close_running)` ("A shift is running (started
     HH:MM, Xh YYm ago). …"). `cancel` → `cancelled`. `close` → quit (session
     kept for recovery). `stop_close` → runs §6.1 with source `close` (can
     chain `over_24h`/`discard_shift`); if that ends `saved`/`discarded` → quit;
     `cancelled`/`error` → stay open and return that result.
   - Every result that quits carries `quit: true`; Python saves the placement
     and destroys the window, so the promise may never resolve.

### 6.9 Settings save — `save_settings(draft)`
One locked transaction (single `_load_raw`/`_save_raw`).
`invalid(default_start_time)` "Default start time must be a valid time (e.g.
09:30)."; `invalid(pay_rate)` "Pay rate must be a positive number (e.g. 20 or
20,50)." (`parse_pay_rate`); `invalid(target_hours)` (must be 1–24);
OSError → `error(save_failed)` "Settings could not be written: …". OK →
`saved{settings, shifts}`. Back/Esc with unsaved changes asks "Save changes?"
(frontend, yes/no/cancel); leaving without saving reverts the appearance
preview via `set_theme`. Pay rate is shown with `repr`-style shortest text
(`20.125` stays `20.125`) — `Settings.pay_rate_text`.

### 6.10 Updates / DLC
Startup: Python checks in the background and emits `update:available`
(app) and `dlc:update` (DLC). One update prompt at a time (frontend guard).
"Version X is available (you have Y). Download and install now? (The app will
close and relaunch automatically.)" → `install_update()`. A non-frozen run
returns `error(not_frozen)` → "Updates can only be installed from the
installed app, not when running from source."
Manual "Check for updates": `check_updates()`; up to date → "You're up to
date (vX)." plus the DLC note when a newer DLC exists.
Update/DLC HTTPS (`services/net.py`) trusts the Windows certificate store plus
certifi's Mozilla roots. A certificate failure comes back as a plain
explanation instead of `CERTIFICATE_VERIFY_FAILED`. A failed check shows an
"Open download page" link and a failed update offers the same
(`open_download_page()`).
DLC section states come from `DlcStatus` (§8).

## 7. Bootstrap payload

```ts
Bootstrap = {
  version, frozen, dev, today, now_epoch_ms,
  settings: Settings, shifts: string[], timer: TimerState,
  dlc: DlcStatus, changelog: ChangelogBlock[] | null, recovery: Recovery | null,
  month: {year, month},          // initial view (today)
  error_log, data_dir, shifts_file
}
```

## 8. Shared shapes

- `WorkEntry {id, date, job_shift, time_in, time_out}` (time_out `""` = open).
- `EntryRow = WorkEntry + {minutes: number|null, overnight, display_date
  ("Tue 23 Sep 2026"), time_out_display ("06:00 +1"), week_key ("2026-W39")}`.
- `TimerState {running, start_iso, start_epoch_ms, job_shift, default_job_shift,
  default_start_time, pay_rate, recovery_pending}` — idle: start fields null.
  The JS clock ticks from `start_epoch_ms`; Python is authoritative on stop.
- `Settings {appearance, default_start_time, pay_rate, pay_rate_text,
  default_job_shift, export_format:'Simple'|'Full', export_include_pay,
  ui_prefs: {lulz:false, reduce_effects:false, lulz_sound:false,
  liquid_glass:false, target_hours:8}}`.
  `lulz_sound` (default off) enables the synthesized fire sound; it only plays
  while Lulz is effective. `liquid_glass` (default off) turns on the iOS-style
  Liquid glass appearance (see `stores/glass.ts`). Frontend and backend ship
  together: `merge_ui_prefs` rejects unknown keys. Bool prefs are read leniently (a non-bool stored
  value falls back to false) but saved strictly (non-bool → `invalid`).
- `DlcStatus {state:'missing'|'ok'|'incompatible', version, update_version,
  message, ocr_available}` (`ocr_available` = Import ▸ From image enabled).
- `OcrCandidate {date, job_shift, time_in, time_out, raw_line, confidence:
  'ok'|'uncertain'}` — the API renames the DLC's `_raw_line`/`_confidence`.
  Uncertain rows are highlighted; all rows start checked.
- `ChangelogBlock {version, items}`.

## 9. `list_month` payload

```ts
MonthData = { year, month, label: "October 2026", pay_rate,
  entries: EntryRow[],          // sorted by date, time_in
  weeks: WeekGroup[],           // ISO-week groups, sorted by (iso_year, week)
  total_minutes, earnings }
WeekGroup = { key:"2026-W39", iso_year, week, entry_ids: string[],
  minutes, earnings }
```
Entries without a time_out count 0 minutes. Empty month → JS shows
"No shifts in {label}. Press START or + Add entry." Totals line:
"Total: H:MM (€x.xx)"; week row "Week N total H:MM (€x.xx)".

## 10. `get_stats` payload

```ts
StatsData = { start, end, granularity, pay_rate,
  buckets: [{key, label, start, minutes, earnings, shifts}],  // every bucket in range, zero-filled
  totals: {minutes, earnings, shifts, worked_days},
  by_shift: [{job_shift, minutes, earnings, shifts}],          // minutes desc
  avg_per_worked_day: {minutes, earnings},
  longest: {entry: EntryRow, minutes} | null,
  open_entries }                                              // entries with no time_out (excluded)
```
Bucket keys: day `2026-10-29` (label "Thu 29"), week `2026-W44` (label "W44",
start = Monday), month `2026-10` (label "Oct 2026"). An entry belongs to its
start date's bucket. `worked_days` = distinct dates with minutes > 0.

## 11. Events (Python → JS)

Single channel: `window.dispatchEvent(new CustomEvent('weleho', {detail:{name,
payload}}))`, emitted only by the `EventBus` pump thread. Subscribe with
`onEvent(name, handler)` from `lib/api`.

| name | payload |
|---|---|
| `close:requested` | `{}` |
| `app:activate` | `{}` — second instance launched; window restored/focused |
| `window:visibility` | `{visible, focused, maximized}` — pause mesh/fire when hidden |
| `update:available` | `{version, current}` |
| `update:installing` | `{version}` |
| `update:failed` | `{message}` |
| `dlc:update` | `{version}` |
| `dlc:status` | `DlcStatus` |
| `timer:changed` | `TimerState` — any timer change not initiated by the awaiting call (e.g. stop during close) |
| `data:changed` | `{reason: 'import'\|'ocr'\|'recovery'\|'restore'}` — refetch month/stats |

## 12. Frontend file ownership

Parallel agents edit **only** their paths. Cross-cutting needs go through the
foundation-owned stores/registries below; ask the foundation owner for changes.

| owner | paths |
|---|---|
| **foundation** | `frontend/` scaffold (package.json, vite/svelte/ts configs, index.html, tests setup), `src/main.ts`, `src/App.svelte`, `src/lib/**` (api: `types.ts`, `index.ts`, `mock.ts`, `flow.ts`; stores; ui primitives incl. `ChoiceModal`, `ConfirmHost`, `Toasts`, `Modal`, `Button`, `TimePicker`, `Calendar`, `Combobox`; theme/tokens; `platform/harden.ts`; `time.ts`; `shortcuts.ts`), `src/fx/MeshBackground.svelte`, `src/fx/Intro.svelte` |
| **timer-agent** | `src/views/timer/**`, `src/fx/fire/**`, `src/views/modals/RecoverShiftModal.svelte`, `src/views/modals/CloseModal.svelte`, `src/views/modals/closeFlow.ts`, `src/views/modals/StopConfirm*.svelte` |
| **entries-agent** | `src/views/entries/**` (table, inline editor, `EntryModal`, `MonthPicker`, import/export actions) |
| **stats-agent** | `src/views/stats/**`, `src/charts/**` |
| **settings-agent** | `src/views/settings/**` (incl. update + DLC flows), `src/views/modals/ChangelogModal.svelte`, `src/views/ocr/**` |

### Foundation-provided seams (in `src/lib/`)
- `api/index.ts`: `api: Api`, `onEvent(name, fn) → unsubscribe`, `ready: Promise<void>`.
- `api/flow.ts`: `runFlow(call: (confirm) => Promise<Result>) → Promise<Result>`.
- `stores/confirm.ts`: `confirm(req) → Promise<choiceId>`,
  `registerConfirmRenderer(kind, Component)` (timer-agent registers
  `StopConfirm*` for `over_24h`/`long_shift`/`stop_shift`; `CloseModal` for
  `close_running`).
- `stores/app.ts`: `bootstrap`, `route` (`'main'|'stats'|'settings'`),
  `navigate(to) → Promise<boolean>` (commits inline edits when leaving main),
  `section` (`'timer'|'shifts'|'stats'`, top-bar segment; below 1080px only the
  active main section shows), `viewMonth {year,month}`, `pageVisible`.
- `stores/settings.ts`: `settings`, `applySettings(s, shifts?)`,
  `saveUiPrefs(partial) → Promise<boolean>`, `dlc`, `shifts`.
- `stores/motion.ts`: `motion: MotionLevel` (`'full'|'reduced'`, from
  reduce_effects + prefers-reduced-motion), `lulz` (forced off under reduced
  motion), `lulzSound` (`lulz && ui_prefs.lulz_sound`), `prefersReducedMotion`.
  `<html>` carries `data-motion` and `data-paused` (page hidden/minimised) for CSS.
- `stores/glass.ts` (re-exported from `stores/app.ts`): Liquid glass state.
  `glassMode: 'off'|'css'|'refract'` is `off` while `ui_prefs.liquid_glass` is
  off or `glassBlock` is set; `css` (tint, sheen and rim, no SVG refraction)
  under `reduce_effects`, after `refractBroken`, or when
  `CSS.supports('backdrop-filter', 'url(#a)')` fails (or the
  `glass/surfaces.ts` `REFRACT_ENABLED` kill-switch is false); else `refract`.
  `glassLive` (`glassMode !== 'off' && motion === 'full'`) gates the pointer
  light, gel press, thumb lens and materialize. `glassBlock:
  'transparency'|'contrast'|null` comes from `prefersReducedTransparency`
  (`prefers-reduced-transparency: reduce`) and `prefersHighContrast`
  (`prefers-contrast: more` or `forced-colors: active`); while set, the
  Settings switch is disabled and the app looks like the option is off.
  `refractBroken` (writable, session-only) is set on lens-map failure or by
  the frame guard. `startGlass()` (started next to `startTheme` in App) puts
  `data-glass="liquid"` on `<html>` in the css and refract modes and
  `data-refract="on"` in refract only; both attributes are deleted (never set
  to `off`) while the mode is `off`.
- Mock flags: `&glass` seeds `liquid_glass: true`; `&glassdebug` (DEV only)
  replaces every lens map with a hard left/right split for alignment checks.
- Liquid glass material (`lib/glass/`, `lib/theme/liquid.css`):
  - `liquid.css` holds the liquid tokens (dark and light, same keys) and the
    shared `.glass` treatment (tint + top sheen, specular conic rim at
    `--lg-light`, inner glow, `--lg-shadow-sit|float|overlay` via the
    `lg-float` / `lg-overlay` classes). Every selector is scoped under
    `[data-glass='liquid']` or `[data-refract='on']` (enforced by
    `tests/liquid.test.ts`), so nothing matches while the option is off.
    Components add their own scoped rules as
    `:global(:root[data-glass='liquid']) .x`; `lg-gel` marks chips that get
    the gel press (`scale` on `--lg-spring`).
  - `use:liquidGlass={'topbar'}` (or `{ key: 'pill', active }`) gives an
    element its own SVG refraction lens in the refract tier: it measures the
    border box, asks `glassRegistry` (`registry.svelte.ts`) for a
    displacement map (`lensMap.ts` pure field, `lensImage.ts` PNG encode,
    shared by key, LRU of 16 idle maps, at most `MAX_LENSES` = 6 lenses) and
    sets `--lg-filter: url(#id)` only once `<LiquidFilters />` has rendered
    that filter. Surfaces are tuned in `surfaces.ts`. `pulseLens(node)`
    briefly over-bends a lens (Segmented thumb press).
  - `<LiquidFilters />` (mounted by App only in refract) renders the filters,
    runs the frame guard (`frameGuard.ts`: median frame > 24ms sets
    `refractBroken`, dropping to the css tier) and drives the pointer light
    (`light.ts`, writes `--lg-light` on registered lens nodes only, while
    `glassLive` and the window is active).
- `stores/modals.ts`: `pushModal(focus) → {id, release}`, `modalOpen` (count),
  `topModal`, `focusTopModal()`. App marks the shell `inert` while
  `modalOpen > 0`.
- `stores/recovery.ts` (§4): `pendingRecovery: Recovery|null`,
  `offerRecovery(rec?)` (no arg → re-reads bootstrap),
  `applyRecoveryResult(r)` (sets timer; clears the pending recovery only when
  the result's `recovery` is null / ok; on error reports and keeps it pending,
  so the modal is re-offered). App shows `RecoverShiftModal` after the intro
  and changelog, keyed on the recovery.
- `stores/confirm.ts` extras: `ConfirmRendererProps<K> {request, onchoose}`,
  `openSheet(Component, props) → Promise<T>` (component gets
  `SheetProps<P,T>` = props + `onclose(result)`), `choose`, `alert`,
  `askYesNo`, `askYesNoCancel`, `reportError(result, title?)`.
- `stores/timer.ts`: `timer: TimerState` + `elapsedSeconds` (1 Hz while
  running, paused when hidden), `setTimer(t)`.
- `stores/entries.ts`: `month: MonthData`, `refreshMonth()`,
  `showEntry(entry)` (jump to its month + select), `selectedId`,
  `setViewMonth(y, m)`, `shiftMonth(delta)`, `goToCurrentMonth()` (all commit
  edits first; resolve false if blocked).
- `stores/toasts.ts`: `toast(msg, {action?, label?, ms=8000}) → id`, `dismiss(id)`,
  `undoAvailable`, `runUndo()` (runs the newest toast action).
- `stores/editGuard.ts`: `registerEditGuard(fn: () => Promise<boolean>)`,
  `commitEdits()`.
- `shortcuts.ts`: `registerCommand(name, fn)`; foundation binds keys. Names:
  `timer.toggle` (F5), `entry.add` (Ctrl+N), `entry.edit` (Enter/F2),
  `entry.delete` (Delete), `undo` (Ctrl+Z), `export` (Ctrl+E), `import.menu`
  (Ctrl+I), `settings.open` (Ctrl+,), `month.prev` (Ctrl+←/PgUp),
  `month.next` (Ctrl+→/PgDn), `month.current` (Ctrl+Home), `settings.save`
  (Ctrl+S), `settings.back` (Esc). Gating as v1.3: nothing while a modal is
  open; month keys not while typing; F5/timer keys not while Settings shows.
  The last registered handler wins (stack); unregister restores the previous.
  App registers fallbacks for `settings.open`, `undo` (`runUndo`),
  `month.prev`/`month.next`/`month.current` before views mount, so views
  override them.
- `ui/index.ts` barrel: `Button`, `Icon`, `Spinner`, `Progress`, `Kbd`,
  `GlassCard`, `Modal`, `ChoiceModal`, `TextInput`, `Field` (+ module export
  `describedBy(id) → '${id}-note'`), `Popover`, `Menu`, `TimePicker`,
  `TimeInput`, `Combobox`, `Calendar`, `CalendarPopover`, `MonthGrid`,
  `Segmented`, `Switch`, `ConfirmHost`, `Toasts`; actions `portal`,
  `clickOutside`, `tooltip`, `focusables`.
- `platform/harden.ts`: `harden() → undo` (blocks browser context menu, zoom, reload/devtools
  keys, file drops and middle-click navigation).

### View components App.svelte mounts

| path | props | exports / notes |
|---|---|---|
| `src/views/timer/TimerView.svelte` | — | Hero ring + start/stop; registers `timer.toggle`. Hidden on `settings` route. |
| `src/views/entries/EntriesView.svelte` | — | Header (month nav, Add, Import ▾, status), table, bottom bar (Edit/Delete/Total/Export). Registers `entry.*`, `export`, `import.menu`, `month.*`; registers edit guard. |
| `src/views/entries/EntryModal.svelte` | `{entry: EntryRow\|null, defaultDate: string, onclose: (saved: EntryRow\|null) => void}` | mounted by EntriesView |
| `src/views/entries/MonthPicker.svelte` | `{year, month, onpick: (y,m)=>void, oncancel}` | mounted by EntriesView |
| `src/views/stats/StatsView.svelte` | — | lazy-loaded on `stats` route |
| `src/views/settings/SettingsView.svelte` | — | `settings` route; registers `settings.save` / `settings.back` |
| `src/views/settings/UpdateFlow.svelte` | — | headless; always mounted; listens `update:*` / `dlc:update` |
| `src/views/modals/ChangelogModal.svelte` | `{blocks: ChangelogBlock[], onclose: () => void}` | shown first after intro |
| `src/views/modals/RecoverShiftModal.svelte` | `{recovery: Recovery, onresolved: (r: RecoveryResult) => void}` | shown after changelog |
| `src/views/modals/closeFlow.ts` | — | `export function handleCloseRequest(): Promise<void>` — App calls on `close:requested` |
| `src/views/ocr/OcrPreviewSheet.svelte` | `{candidates: OcrCandidate[], errors: string[], shifts: string[], onclose: (r: OcrSaveResult\|null) => void}` | opened by `openOcrImport()` exported from `src/views/ocr/ocrImport.ts`, which EntriesView's Import ▾ calls |
| `src/fx/fire/FireLayer.svelte` | `{running, elapsedSeconds, burst: number}` | lazy; TimerView mounts only when `lulz` on |
