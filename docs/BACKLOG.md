# Työaikaweleho — Backlog

The single list of future work. Each idea is one row; bigger ones get a design
doc in `docs/` once they are planned.

| Idea | Status | Rough size | Depends on | Plan |
|---|---|---|---|---|
| Achievements — badges earned from logged hours, shown in Stats | done | M | — | [V2_GAMIFICATION_PLAN.md](V2_GAMIFICATION_PLAN.md#achievements) |
| Work pet — the wizard as a companion that gains energy as hours pile up | done (auras later) | L | Achievements | [V2_GAMIFICATION_PLAN.md](V2_GAMIFICATION_PLAN.md#work-pet) |
| Pet looks — unlocked by pet level, plus an after-shift bazooka | done (2.1.4) | M | Work pet | [V2_GAMIFICATION_PLAN.md](V2_GAMIFICATION_PLAN.md#work-pet) |
| **2.1.4 Groundwork** — tolerant entry reader (unknown entry keys survive load, save and undo); default shift no longer falls back to "GPSR" | done (2.1.4) | S | — | [V2_ACCURATE_PAY_PLAN.md](V2_ACCURATE_PAY_PLAN.md#214--groundwork-a-tolerant-entry-reader) |
| **2.2 Accurate pay** — pay-rate history with effective dates; unpaid breaks with an optional auto rule; a note per shift | planned | L | 2.1.4 | [V2_ACCURATE_PAY_PLAN.md](V2_ACCURATE_PAY_PLAN.md) |
| **2.3 Timesheet day** — names on the EAS sheet; shift manager (rename, hide, reorder); date-range and CSV export; restore from backup | planned | M | 2.2 (soft) | [V2_TIMESHEET_DAY_PLAN.md](V2_TIMESHEET_DAY_PLAN.md) |
| **2.4 Never forget the timer** — tray icon; "still running after N h?" and "forgot to start?" notifications; opt-in autostart; Pause (feeds the break) | idea | M–L | 2.2 | — |
| **2.5 Suomeksi** — Finnish/English switch with a string catalogue and Finnish dates; the EAS sheet stays English | idea | L | — | — |
| **2.6 Time balance** — daily/weekly target and a running saldo; absences (sick, holiday); Finnish public holidays computed locally; holidays never break streaks or drain the pet | idea | L | 2.2 | — |
| **2.7 Pay supplements** — evening / Saturday / Sunday supplements by time window; rules differ by collective agreement, so ask the users first | idea | L–XL | 2.2 | — |
| Accounts / login — local accounts with encrypted per-user data | planned | L | — | [V2_AUTH_PLAN.md](V2_AUTH_PLAN.md) |
| Cloud sync — the same data on several PCs | planned | XL | Accounts / login, 2.1.4 | [V2_SYNC_PLAN.md](V2_SYNC_PLAN.md) |

The numbered releases are ranked by value to the people using the app (the
monthly timesheet and the money on it) against risk; source: planning
session, 2026-11-05. 2.4–2.7 get their own design docs when picked up.

**Status:** idea → planned (has a design doc) → in progress → done.
**Size:** S = an evening, M = a few days, L = a week or two, XL = more.

## How to add an idea

1. Add a row with status *idea*, and a line under *Ideas parking lot* or a
   note on where it came from and when (e.g. "chat, 2026-10-30").
2. When it is picked up, write a design doc (`docs/V2_<NAME>_PLAN.md`, same
   layout as the existing ones: Why, Goals / non-goals, design, Data model
   changes, Migration, Testing plan, Implementation order), link it here and
   set the status to *planned*.
3. Move it to *done* when it ships, with the version number.

## Ideas parking lot

Small ideas not committed to yet, good filler between releases. Most fall out
of the achievements engine for free. Do the hour-based ones **after 2.2** so
they count net hours (after breaks) from the start:

- **Personal records in Stats** — longest shift, best week, best month
  (done in the Achievements sheet's Hall of fame; a Stats tile is still open).
- **Streaks on the Stats KPI tiles** — current run of workdays at target.
- **Tool achievements** — first Excel export, first OCR import (need event
  counters; v2 of achievements).
