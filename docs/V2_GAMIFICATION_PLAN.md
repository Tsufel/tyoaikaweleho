# Työaikaweleho v2.x — Achievements and a work pet (design plan)

> Status: **planning** — nothing in this document is implemented yet.
> Listed in [BACKLOG.md](BACKLOG.md). Interacts with [V2_SYNC_PLAN.md](V2_SYNC_PLAN.md)
> (the new keys should sync).
> Original ideas (chat, 2026-10-30): *"Tulevaisuudes voi sit laittaa achievements
> ym."* and *"asennat tonne jonku lemmikin mikä saa virtaa ku tulee tuntei kasaa
> jne"* — add achievements, and a pet that gains energy as worked hours pile up.

## Why

Logging hours is a chore. The app already has a personality — the wizard
mascot, Lulz fire, milestone flares — and a little long-term reward on top of
it (badges to collect, a companion that grows with you) makes opening the app
something to look forward to rather than a duty.

## Goals / non-goals

| Goals | Non-goals |
|---|---|
| Fun, light, opt-in (the pet is off by default, like Lulz) | Punishing rest: no streak-loss shaming, no pet that "dies" |
| Everything derived from the real, stored entries | Guilt notifications or nagging to work more |
| Respects reduced motion and pauses when hidden | Dark patterns, currencies, anything bought |
| No extra disk writes while the timer ticks | Leaderboards or sharing (needs accounts/sync first) |
| Works offline, no new dependencies | Achievements for tool use in v1 (they need counters) |

## Core principle: derive, don't count

Not every write path tells the frontend about it: a normal stop, a manual
save, an inline edit and a delete emit no event (`webapp/api.py`); only
recovery, restore, import and OCR emit `data:changed`. Counting progress up
from events would drift. Instead all progress is computed from the stored
entries by a pure engine, the same way `stats.summarize` works. The only new
stored state is *what has already been celebrated* and the pet's settings.

## Achievements

### Engine

A new pure module `achievements.py` next to `stats.py`:

- Input: all entries, `target_hours` (`ui_prefs`), `pay_rate`, today.
- Output per achievement: `{id, title, desc, icon, tier, progress: {cur, goal},
  met_on}` where `met_on` is the date the condition first became true when
  replaying entries in date order (`None` if not met).
- Reuses `utils.entry_minutes` (overnight-aware) and the day/week bucketing
  from `stats.summarize`. An entry counts on its start date, as in Stats.
- Open entries (no `time_out`) are ignored, as in Stats.

### Catalogue v1 (~20, all derivable from entries)

| Group | Achievements |
|---|---|
| Getting started | First shift saved |
| Total hours | 10 h · 100 h · 500 h · 1000 h |
| Consistency | 5 workdays in a row at target · 4 weeks in a row with a shift |
| Daily target | Target hit on 10 days · on 50 days |
| Shift types | First overnight shift · 12 h marathon · Early bird (start before 06:00) · Night owl (finish after 22:00) |
| Earnings | €1 000 earned · €10 000 earned |
| Lulz | Reach the *inferno* tier (`fireBadge`) · Clock out in blue overtime fire |

- Earnings achievements are flagged: `pay_rate` is global and rewrites past
  earnings, so they are only unlocked, never revoked (see *Persistence*).
- "In a row" counts **workdays** (Mon–Fri), so weekends never break a run.
- Lulz achievements are checked from the saved shift's length against the same
  thresholds `fireBadge` / `milestonesFor` use, so they don't need Lulz to have
  been on.
- Deferred to v2: tool achievements (first Excel export, first OCR import,
  first import) — they need event counters stored in `data.json`.

### Persistence

- New top-level key `achievements_seen: {id: "YYYY-MM-DD"}` in `data.json`.
  Being in `data.json` means it is covered by `.bak` and the 14 daily
  snapshots (`storage._save_raw` / `_daily_snapshot`) with no extra work.
- Written only when the frontend acknowledges an unlock — never on a timer tick.
- Once seen, an achievement stays unlocked even if entries are later edited,
  deleted or the pay rate changes. Unseen ones are recomputed every time.
- **First run backfill:** the first time the feature runs, everything already
  met is marked seen silently, then one toast: *"You've already earned N
  achievements"* — no wall of 15 toasts for long-time users.

### API (add to `docs/V2_UI_API.md` when built)

| method | returns |
|---|---|
| `get_achievements()` | `ok{items, newly}` — `newly` = met but not yet seen |
| `ack_achievements(ids)` | `ok` — stores them in `achievements_seen` |

The frontend calls `get_achievements()` on bootstrap, after `stopShift`
returns `saved` (`frontend/src/views/timer/timerActions.ts`), after entry
saves/edits/deletes and on `data:changed`.

### UI

- **Stats:** a 🏆 *12 / 24* KPI tile in `StatsView.svelte` opens an
  `AchievementsSheet` via `openSheet` (`lib/stores/confirm.ts`): unlocked ones
  with dates, locked ones with a progress bar, hidden ones as "???".
- **Unlock:** `toast('🏆 100 hours!', {tone: 'success', label: 'View', action:
  openAchievements})` (`lib/stores/toasts.ts`); with Lulz on, also a
  `milestone` flare via `emitFx` (`fx/fire/fxBus.ts`) so it gets the full fire
  treatment.

## Work pet

### Character

The wizard (`frontend/src/assets/wizard.webp`) is already the app's mascot, so
he becomes the pet: a familiar the user can name. He grows through stages by
level — **apprentice → wizard → archmage** — and achievements unlock
cosmetics (hats, robe colours, a staff glow).

### Meters (derived, never stored)

- **Energy 0–100** — "gets power as hours pile up":
  hours worked in the last 7 days ÷ (target × the user's usual workdays in
  that window). Usual workdays = weekdays the user has actually worked on in
  the last 8 weeks, so days they never work never drain it. It charges live
  while the timer runs, from the elapsed time already in `stores/timer`.
- **XP / level** from lifetime hours on a gentle curve, e.g. level *n* needs
  `10 · n^1.5` hours total (level 10 ≈ 316 h, level 20 ≈ 894 h).

### Moods

| Mood | When |
|---|---|
| Sleeping | No timer running and outside usual hours, or a few days without shifts. Wakes up happy — no penalty, no sad face |
| Idle | Default when the app is open and no timer runs |
| Working | Timer running; energy fills visibly |
| Hyped | Lulz on and the shift is "on fire" or beyond (`fireBadge`) |
| Celebrating | Short reaction to fxBus `blast` (shift saved) and `milestone` |

### Placement and setting

- A small corner companion on `TimerView.svelte` beside the ring; clicking it
  opens a pet sheet with energy, level, progress to the next stage and the
  cosmetics wardrobe.
- An opt-in **Pet** switch in Settings, off by default. State lives in a new
  top-level `pet: {enabled, name, cosmetics}` in `data.json`, added in the same
  places a `ui_prefs` key is: `storage.py` defaults / allowlist and
  `_check_setting`, `frontend/src/lib/api/types.ts`, `lib/stores/settings.ts`.

### Motion

Follows the existing guards: animates only when `motion === 'full'`
(`lib/stores/motion.ts`), pauses with `animationsActive` (hidden or
unfocused window), and shows static poses when motion is reduced.

### Open question: art

Either drawn/commissioned sprite states for each mood and stage, or start with
an animated SVG/CSS version of the current wizard and replace it later. The
logic does not depend on the choice.

## Data model changes

- Two new optional top-level keys in `data.json`: `achievements_seen`, `pet`.
- No change to entries.

## Migration

- Clean on read with defaults for missing keys — the existing pattern; there is
  no schema version.
- Downgrade is safe: `storage._load_raw` / `_save_raw` load and rewrite the
  whole dict, so an older version keeps unknown top-level keys untouched.

## Sync interaction

`achievements_seen` and `pet` belong in the *synced settings* list of
[V2_SYNC_PLAN.md](V2_SYNC_PLAN.md). Merge rule for `achievements_seen`: union
of ids, earliest date wins.

## Testing plan

- `tests/test_achievements.py` — every catalogue rule on fixture entries,
  including overnight shifts, run edges across weekends, open entries ignored,
  first-run backfill and permanence after an entry is deleted.
- `tests/test_api_contract.py` — `get_achievements` / `ack_achievements`
  shapes, unknown ids rejected.
- `frontend/tests/achievements.test.ts` — unlock toasts shown once, backfill
  toast once.
- `frontend/tests/petLogic.test.ts` — energy curve, days off never drain,
  level curve, mood selection, reduced motion = static.

## Implementation order

1. `achievements.py` engine and tests.
2. API, `achievements_seen` persistence and first-run backfill.
3. Stats tile, `AchievementsSheet`, unlock toasts (+ Lulz flare).
4. Pet logic as a pure module (energy, level, mood) with tests.
5. Pet companion on the Timer view, pet sheet, Settings switch.
6. Art pass.
7. Cosmetics unlocked by achievements.
