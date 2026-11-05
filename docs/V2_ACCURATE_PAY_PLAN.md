# Työaikaweleho v2.x — Accurate pay: rate history, breaks, notes (design plan)

> Status: **planning** — nothing in this document is implemented yet.
> Releases: **2.1.4** (groundwork, below) then **2.2** (the features).
> Listed in [BACKLOG.md](BACKLOG.md). Interacts with
> [V2_SYNC_PLAN.md](V2_SYNC_PLAN.md) (new keys sync) and
> [V2_GAMIFICATION_PLAN.md](V2_GAMIFICATION_PLAN.md) (badges and the pet count
> net hours). Source: planning session, 2026-11-05.

## Why

The app's job is the monthly timesheet and the money on it, and today three
things make that number wrong:

- **One pay rate for all of history.** `pay_rate` is a single global value
  that Stats (`stats.summarize`), the month view (`controller.list_month`),
  the export and the earnings badges (`achievements.evaluate`) multiply every
  past shift by. A raise silently rewrites every past month's earnings.
- **No breaks.** A shift is `time_out − time_in`. Unpaid lunch is common, so
  people either fudge their times or over-report.
- **No notes.** There is nowhere to write "covered for Mia" or "training in
  Tampere", so people keep a second list.

## Goals / non-goals

**Goals**
- Past earnings never change when the rate changes, unless the user asks to
  correct history.
- A break per shift, typed or added by an optional rule, that every total
  (hours, €, target days, the pet) respects.
- A short note per shift, shown in the month list and the Simple export.
- Old data keeps working with no migration step; entries nobody touches stay
  exactly as they are on disk.
- Going back one version (2.2 → 2.1.4) never crashes or loses fields.

**Non-goals**
- Pay supplements (evening / Saturday / Sunday) — 2.7, separate plan.
- Several breaks per shift with their own times; one total is enough.
- Taxes, deductions, payslips.
- Per-shift-type rates (a rate per job/shift). Possible later on top of the
  same `rate_on` seam.

## 2.1.4 — Groundwork: a tolerant entry reader

**Blocker found while planning.** `storage._entry` builds
`WorkEntry(**{**e, "date": …})` (`storage.py`, `_entry`). `WorkEntry` is a
dataclass with exactly five fields, so an entry with **any** other key raises
`TypeError` in `load_month` / `load_all_entries`, and with them `list_month`,
Stats, achievements, the pet and export all fail. Every released version
behaves this way. So the first version that writes a new entry field would
break anyone who goes back a version — and the same applies to the sync
plan's `updated_at` and tombstones.

Fix, shipped alone as 2.1.4 a few weeks ahead of 2.2 so most installs have
it before any new field is written:

- `WorkEntry` gains `extra: dict = field(default_factory=dict, compare=False)`.
- `_entry` puts every key it doesn't know into `extra`.
- `storage.save_entry` writes `{**entry.extra, **known_fields}`.
- `results.work_entry_dict` and `controller.restore_entry` (undo delete)
  carry `extra` through instead of whitelisting the five keys, so undo
  doesn't strip fields either.
- Also in 2.1.4: `storage.get_default_job_shift` stops falling back to
  `"GPSR"` (no longer in `_DEFAULT_SHIFTS`); see
  [V2_TIMESHEET_DAY_PLAN.md](V2_TIMESHEET_DAY_PLAN.md) for the full fix.

Tests: an entry with an unknown key loads, round-trips through
`save_entry`, `update_entry_field`, delete + `restore_entry`, and appears in
`list_month` / Stats / export unchanged.

## Design (2.2)

### Pay-rate history

New top-level key:

```json
"pay_rates": {"rows": [{"from": "2000-01-01", "rate": 20.0},
                       {"from": "2026-09-01", "rate": 21.5}],
              "mirror": 21.5}
```

- `rows` sorted by `from`; `rate_on(d)` = the rate of the last row with
  `from <= d`; dates before the first row use the first row.
- **Derived on first read**: when `pay_rates` is missing it is
  `{rows: [{from: "2000-01-01", rate: pay_rate}], mirror: pay_rate}`.
  Nothing is written until the user changes a rate.
- **Old-version mirror.** Every write also sets top-level `pay_rate` (what
  2.1.x reads) to the rate in effect today, and `mirror` to the same value.
  If on read `pay_rate != mirror`, an older version changed the rate since,
  so a row `{from: today, rate: pay_rate}` is appended. The mirror (not
  "rate in effect today") is compared so a future-dated raise becoming due
  isn't mistaken for an old-version edit. This is the same idea as the
  `window_geometry` legacy key.
- **Changing the rate** in Settings asks (confirm kind `pay_rate_change`):
  *From today* (default) / *From date…* / *Correct all history* (replaces
  every row — for typos). Settings also gets a small history list: add a
  row (future dates allowed), delete a row (not the last one).
- A `PayRates` helper in `storage.py` (`get_pay_rates()`, `.on(date)`,
  `.current()`); `get_pay_rate()` stays as `.current()` for callers that
  only need today's rate (timer card, Lulz).

### Breaks

Entry fields, written **only when non-default** so untouched entries stay
five keys:

- `break_minutes: int` — `0 ≤ b < gross minutes`.
- `break_auto: bool` — the value came from the rule, not the user.

Top-level `break_rule: {"enabled": false, "min_shift_minutes": 360,
"deduct_minutes": 30}` — off by default, preset to the common Finnish
convention (30 min on shifts of 6 h or more) when switched on.

- The rule is **stamped, not derived**: it runs when a shift is closed —
  `timer_stop`, `recovery_resolve('save')`, `save_entry` for a new closed
  entry, Excel import and OCR save (the OCR preview says so). Changing the
  rule never rewrites past entries.
- `update_entry_field` (inline time edit) re-runs the rule only when
  `break_auto` is set. Typing a break clears `break_auto`.
- `utils.net_minutes(e) = max(0, entry_minutes(e.time_in, e.time_out) −
  e.break_minutes)`.
  `entry_minutes` stays gross.
- The live timer shows gross; the stop summary says "30 min break deducted"
  with an edit link.

### Notes

- Entry field `note: str`, only when non-empty. Single line, trimmed, at most
  200 characters, cleaned with the same control/bidi filter as `pet_name`
  (`storage._BAD_NAME_CATEGORIES`).
- Shown as an icon with a tooltip in the month list, editable in
  `EntryModal`. Not in the EAS export.

### Net or gross — who counts what

| Consumer | Uses |
|---|---|
| Month totals, week rows, Stats hours/€/avg/target days | net |
| Earnings everywhere | net × `rate_on(entry date)`, summed per entry, rounded once |
| Achievements: hours, earnings, target-day and streak badges | net |
| Achievements about the clock: overnight, early bird, night owl, marathon, inferno, blue flame | gross (they are about when and how long you were there) |
| Pet (`achievements.pet_stats`: lifetime, 8-week days) | net |
| Live timer ring, Lulz fire | gross |

Badges already seen stay unlocked (`with_seen`), so a user who suddenly
logs breaks never loses one.

### Code impact

| File | Change |
|---|---|
| `storage.py` | `WorkEntry` fields; `PayRates`; `break_rule` getter/setter; mirror logic in `_load_raw` / setters |
| `utils.py` | `net_minutes`, `apply_break_rule(entry, rule)` |
| `stats.py` | `summarize(..., rates)` — earnings per entry with `rates.on(d)`; minutes net; payload `pay_rate` = current rate, new `mixed_rates: bool` |
| `webapp/controller.py` | `list_month` sums € per entry; rows get the new fields; the rule at every close path; `pay_rate_change` confirm; settings payload gains `pay_rates`, `break_rule` |
| `webapp/results.py` | `entry_row`: `minutes` (net), `gross_minutes`, `break_minutes`, `break_auto`, `note`, `earnings` |
| `achievements.py` | `evaluate(entries, target, rates, today)` takes the rate callable; net/gross per the table; `pet_stats` net |
| `excel_export.py` | Simple: E = net hours, F "Break" and G "Note" only when the month has any (column B stays as `import_excel._detect_format` expects); Full/EAS: (HOURS) = net, a BREAK column only in months with breaks, H8 = rate at month end plus "Rate x from d.m." lines when mixed; totals summed per entry |
| `import_excel.py` | read the Break column when present; apply the rule otherwise |
| Frontend | `types.ts`, `mock.ts`; `EntryModal` (Break, Note), `EntriesView` (break chip, note icon), `ShiftSummary` / stop confirm, Settings *Timer & Pay* (rate history, break rule), Stats mixed-rate hint |

## Data model changes

- Entries: optional `break_minutes`, `break_auto`, `note`.
- Top level: `pay_rates`, `break_rule`. `pay_rate` stays, kept in step.

## Migration

- No migration step: missing keys are derived on read (the existing
  clean-on-read pattern, no schema version).
- **Downgrade table**

| Going back to | What happens |
|---|---|
| 2.1.4+ | Works. Entry extras kept on save; earnings shown at today's rate (the old behaviour); breaks ignored, so hours look gross. A rate changed there is picked up by 2.2 via the mirror. |
| ≤ 2.1.3 | **Crashes on any entry with a break or note** (`TypeError` in `_entry`). Not supported; the updater only moves forward. This is why 2.1.4 ships first. |

## Sync interaction

`pay_rates` and `break_rule` are synced settings (whole value, newer wins);
`pay_rates.mirror` is local. Entries merge as whole records, so `extra`
carries the new fields with no per-field logic. See
[V2_SYNC_PLAN.md](V2_SYNC_PLAN.md).

## Testing plan

- `tests/test_storage.py`: unknown entry keys round-trip (2.1.4); pay-rate
  derivation, mirror detection, future-dated rows; break/note cleaning and
  "only when non-default".
- `tests/test_stats.py`: earnings across a rate change mid-range and
  mid-month; net minutes; `mixed_rates`.
- `tests/test_achievements.py`: earnings badges use per-date rates; net vs
  gross badges; seen badges survive adding breaks.
- `tests/test_excel_export.py`: no-break months keep the exact current
  layouts (cell-by-cell); Break/Note columns; mixed-rate lines;
  `import_excel` still detects both layouts.
- `tests/test_controller.py`: the rule at every close path, never on past
  entries; `break_auto` cleared by a typed break; `pay_rate_change` options.
- `tests/test_api_contract.py`: new row and settings fields.
- Frontend: `EntryModal`, `EntriesView`, Settings rate history, stop summary.

## Implementation order

1. 2.1.4: tolerant reader + undo/restore carry `extra` + GPSR fallback. Ship.
2. `PayRates` + mirror, `rate_on` in Stats, `list_month`, achievements, export.
3. `break_minutes` / `break_auto`, `net_minutes`, the rule at close paths.
4. Notes.
5. Export columns and import of the Break column.
6. UI: modal, list chips, Settings, stop summary, Stats hint.
7. Release 2.2 with a changelog entry explaining the rate history.

## Open questions (with the default we go with)

- *Are their breaks actually unpaid?* — Unknown per workplace, so the rule is
  off by default and typed breaks are optional.
- *Will the employer accept a changed EAS sheet?* — Only months with breaks
  get the extra column; others are byte-for-byte the current layout.
- *What does editing the rate field mean?* — "From today", with the other two
  options one click away.
