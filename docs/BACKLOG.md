# Työaikaweleho — Backlog

The single list of future work. Each idea is one row; bigger ones get a design
doc in `docs/` once they are planned.

| Idea | Status | Rough size | Depends on | Plan |
|---|---|---|---|---|
| Achievements — badges earned from logged hours, shown in Stats | planned | M | — | [V2_GAMIFICATION_PLAN.md](V2_GAMIFICATION_PLAN.md#achievements) |
| Work pet — the wizard as a companion that gains energy as hours pile up | planned | L | Achievements | [V2_GAMIFICATION_PLAN.md](V2_GAMIFICATION_PLAN.md#work-pet) |
| Accounts / login — local accounts with encrypted per-user data | planned | L | — | [V2_AUTH_PLAN.md](V2_AUTH_PLAN.md) |
| Cloud sync — the same data on several PCs | planned | XL | Accounts / login | [V2_SYNC_PLAN.md](V2_SYNC_PLAN.md) |

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

Small ideas not committed to yet. Most fall out of the achievements engine
for free:

- **Personal records in Stats** — longest shift, best week, best month.
- **Weekly recap** — a short "this week" card on the first open of a new week.
- **Streaks on the Stats KPI tiles** — current run of workdays at target.
- **Tool achievements** — first Excel export, first OCR import (need event
  counters; v2 of achievements).
