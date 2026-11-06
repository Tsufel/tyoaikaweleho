# Työaikaweleho v2.x — Achievements and a work pet (design plan)

> Status: **achievements built** (engine, API, persistence, Stats tile, sheet,
> unlock card). **Pet built** (logic, prefs, Settings control, Timer companion,
> pet sheet), and pet looks unlocked by level with the after-shift bazooka;
> auras (step 8) not yet.
> **Coming in 2.2** ([V2_ACCURATE_PAY_PLAN.md](V2_ACCURATE_PAY_PLAN.md)):
> hours count **net** of breaks, and earnings use the rate on each shift's
> date — see *Net hours and per-date rates* below.
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
- Output per achievement: `{id, title, desc, icon, tier, hidden, progress: {cur,
  goal, unit}, met_on}` where `met_on` is the date the condition first became true when
  replaying entries in date order (`None` if not met).
- Reuses `utils.entry_minutes` (overnight-aware) and the day/week bucketing
  from `stats.summarize`. An entry counts on its start date, as in Stats.
- Open entries (no `time_out`), zero-length shifts and entries dated after today
  are ignored.

### Catalogue (28, all derivable from entries)

| Group | Achievements |
|---|---|
| Getting started | First shift saved · 100 shifts (*Centurion*) |
| Total hours | 10 h · 100 h · 250 h · 500 h · 1000 h · 2500 h |
| Consistency | 5 workdays in a row at target · 10 in a row (*Fortnight*) · 4 weeks in a row with a shift · 12 weeks (*Seasoned*) |
| Daily target | Target hit on 10 days · on 50 days |
| Shift types | First overnight shift · 12 h marathon · Early bird (start before 06:00) · Night owl (finish after 22:00) |
| Earnings | €1 000 earned · €10 000 earned |
| Lulz | Reach the *inferno* tier (`fireBadge`, ≥ 125 % of target) · Clock out in blue overtime fire (past the target, as `FxDirector` colours the blast) |
| Calendar | Friday the 13th · *Joulutonttu* (24–26 December) · *1337* (start at exactly 13:37) · *Double header* (two shifts on one day) · *No days off* (all 7 days of one ISO week) · *One year in* (a shift 365+ days after the first) |

Hidden until met ("???" with the `hidden_<tier>` medal): first overnight,
early bird, night owl, marathon, both Lulz ones and all the calendar ones.
Calendar ones go by the shift's start date, like everything else, so an
overnight shift from Thursday the 12th is not a Friday the 13th one.

- **Medal art:** `icon` defaults to the id. The milestones added later (250 h,
  2500 h, Centurion, Fortnight, Seasoned and the calendar ones) set `icon` to
  an earlier medal in the catalogue (e.g. 250 h shows the 100 h medal) until
  they get art of their own; the hidden ones still show `hidden_<tier>` until met.

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
- **First run backfill:** while `achievements_seen` is absent,
  `get_achievements()` reports `first_run: true`; the frontend shows one toast,
  *"You've already earned N achievements"*, and acks all of `newly` (an empty
  ack still ends the first run) — no wall of 15 toasts for long-time users.

### API ([V2_UI_API.md](V2_UI_API.md) §5, §10.1)

| method | returns |
|---|---|
| `get_achievements()` | `ok{items, newly, first_run}` — `newly` = met but not yet seen |
| `ack_achievements(ids)` | `ok` — stores the met ones in `achievements_seen` with their `met_on` |

The frontend (`lib/stores/achievements.ts`) calls `get_achievements()` once
after the intro, then again (debounced 350 ms, coalesced) whenever the viewed
month is re-read — every save, stop, edit, delete, import and `data:changed`
path ends in `refreshMonth` — and when `pay_rate` or `target_hours` change.
That avoids hooking each write path separately.

Nothing pops up during a shift (or while an unfinished one waits to be
recovered). A check still updates the sheet and the tile, but it queues no
cards, shows no toasts and acks nothing, so Python keeps listing those unlocks
in `newly`. When the shift ends (End shift, a discard, a recovery, or a stop
from elsewhere), the store checks again and the shift's unlocks pop up then;
closing the app mid-shift celebrates them on the next launch. A queued card
that hasn't shown yet waits for the end of the shift too, while one already on
screen (and so already acked) finishes. A first run met mid-shift
notes what is met then as the backfill but acks nothing either, so the first
run (and its summary toast) survives closing the app; when the shift ends the
backfill is acked with its toast, and what the shift itself earned gets cards.

### UI

- **Medals:** one Gemini-made medal per achievement plus a `hidden_<tier>`
  medal, cut out to `frontend/src/assets/medals/<icon>.webp`.
- **Stats:** a 🏆 *11 / 28* KPI tile in `StatsView.svelte` with the three
  latest medals opens `AchievementsSheet` via `openSheet`: grouped by tier,
  unlocked ones with dates, locked ones greyed with a progress bar, hidden ones
  as "???". At the top, a *Hall of fame* (`RecordsPanel.svelte`, from
  `get_records`, [V2_UI_API.md](V2_UI_API.md) §10.3) lists personal records:
  longest shift, best day, week and month, busiest week, earliest start,
  latest finish, best workday streak and the first shift's date.
- **Unlock:** `AchievementUnlock.svelte` (mounted in `App.svelte`) shows a card
  under the title bar: the medal flips in, glows, gets a shine sweep and a
  spark burst in the tier colour; with Lulz on, also a `milestone` flare via
  `emitFx`. It waits ~0.9 s (so it doesn't land on the clock-out blast), waits
  for a running shift to end, pauses while a modal is open, the window is
  hidden or the pointer is on it, and
  clicking it opens the sheet. Reduced motion shows it still.
- **Batches:** more than 3 new unlocks at once (e.g. an import) animate only
  the 3 rarest; the rest are summed up in one *"…and N more achievements
  unlocked"* toast. The first-run backfill is one toast instead.

## Work pet

### Art (done)

Pixel art made with Gemini, two characters with the same four poses:

| Pose | Familiar (winged cat in a star hat) | Wizard |
|---|---|---|
| `idle` | standing with a staff | standing, pointing, staff |
| `fly` | on a broom, wide awake | on a broom, waving |
| `drowsy` | on a broom, eyes half shut, *zZ* | on a broom, nodding off, *zZ* |
| `sleep` | curled up asleep | face down asleep, staff dropped |

The originals are 2048 px JPGs on white with ~22.76 px art pixels. They are
rebuilt at a 180-cell grid (the wizard has some half-cell steps; on the
familiar this just doubles each pixel), the white background connected to the
border is made transparent, and each character's four poses are cropped to one
shared box so swapping poses never shifts the sprite. Output:
`frontend/src/assets/pets/<character>_<pose>.webp`, lossless, ~10 KB each,
familiar 142×122, wizard 162×140, drawn with `image-rendering: pixelated`.

**Looks (2.1.3):** more pictures of the same characters, recoloured or
holding a bazooka, are cut the same way by `scripts/pet_sprites.py` into
`<character>_<pose>_<look>.webp` (its `SOURCES` maps each sprite to its
source picture; re-run `scripts/pet_particles.py` after it, which treats
small dark islands as sleep z's only when they aren't vivid, so the looks'
coloured sparkles stay sparkles). The box stays the
character's; art that reaches past it (the classic and neon familiar
bazookas, the neon wizard's) grows the sprite by whole art pixels, and `SKIN_ART` in `petSkins.ts` tells `PetSprite` to draw those
overhanging the box so the pet never shifts.

### Character and name

Settings → **Pet**: *Off* (default) · *Familiar* · *Wizard*, plus an editable
name (defaults *Tähti* for the familiar — it wears the star hat — and *Weleho*
for the wizard). The familiar is the "pet" of the original idea; the wizard is
there for people who want the mascot himself.

### Meters (derived, never stored)

- **Energy 0–100** — "gets power as hours pile up": hours worked in the last
  7 days ÷ (target × the user's usual workdays in that window). Usual workdays
  = weekdays the user actually worked on in the last 8 weeks, so days they
  never work never drain it. Charges live while the timer runs, from
  `elapsedSeconds` in `stores/timer`.
- **XP / level** from lifetime hours: level *n* needs `10 · (n−1)^1.5` h in total (level 1 at 0 h, level 2 at 10 h)
  (level 10 ≈ 270 h, level 20 ≈ 828 h). Shown as *Lv 12* on the pet sheet.
- **Rank title** by level instead of new sprites: Apprentice (1–4) →
  Adept (5–9) → Wizard (10–19) → Archmage (20+), e.g. *"Tähti, Adept
  familiar"*.

### Pose (state machine)

One pose at a time, picked by a pure `petPose(input)` in `petLogic.ts`:

| Pose | When | Why |
|---|---|---|
| `fly` | Timer running, under 75 % of the daily target (`TIRED_AT`) | "Working", flying along with you, fresh |
| `drowsy` | Timer running and 75 % of the target or more, overtime included | Tires towards the end of the shift (6 h of 8) — a gentle hint, never a warning or a sound |
| `idle` | No timer, 06:00–22:00 | Ready for the next shift |
| `sleep` | No timer and 22:00–06:00, or no shift on any of the last 3 usual workdays (holiday) | Napping on days off; wakes up happy, no penalty or sad face |

Energy never picks a pose, so a quiet week can't make the pet look sad. It is
only shown on the sheet.

### Animation (CSS only, on the static frames)

`PetSprite` stacks the one frame several times, each copy clipped to one part,
so parts move on their own with no extra art: the body splits at a seam row
(`petSpriteLayers.ts`; the lower copy reaches one art pixel up under the upper
so the clip edges never show), and every sparkle and z the art already has is
its own copy. `scripts/pet_particles.py` finds those floating bits in the
sprites and writes their boxes to `petParticles.ts`; re-run it after changing
the art (a test fails when the file is stale). Moves are whole art pixels in
`step-end` steps, like frame-by-frame sprite animation.

| Pose | Loop |
|---|---|
| `idle` | Breathing: the rows above the seam drop one art pixel and back (1.8 s); the staff (and the wizard's hand on it), the familiar's yellow star and the wizard's raised pointing hand stay put, drawn on top as a still copy, so the staff doesn't shrink with each breath; sparkles twinkle |
| `drowsy` | Nodding off: the head sinks one pixel, then two, and snaps back up (3.2 s); the *z*'s float up in turn |
| `sleep` | Slow breathing (3.6 s); the *z*'s float up, drift a pixel and fade |
| `fly` | Hover up and down two pixels (1.6 s), the shadow shrinking as it rises; the broom sparkles trail off behind |

- **Pose change:** a pixel puff (8 square particles) hides the swap, then the
  new pose lands with a squash.
- **Reactions:** a hop and a sparkle burst after every saved shift (the
  `burst` store, also bumped by manual saves), on fxBus `milestone` (Lulz) and
  on an achievement unlock.
- **Petting:** clicking the pet makes it hop and shows a pixel heart; a long
  press, the context menu or the keyboard (Enter / Space) opens the pet sheet.
  Petting is the point.
- **Tired sighs:** while `drowsy`, a pixel speech bubble (`PetBubble`) over
  the pet says one of *"Oispa kaljaa"*, *"Oispa perjantai"*, *"Koht himaan"*
  (`TIRED_LINES`) 4 s in and then every 10 minutes, for 6 s each, never the
  same line twice in a row and not while the app is hidden. Petting a tired
  pet sighs too. On Fridays *"Oispa perjantai"* is left out. The bubble goes
  as soon as the pose changes.
- **Friday fly-by (easter egg):** a shift saved on a Friday, or one that
  started on a Friday and ran past midnight (`fridayShift`), sends the pet
  across the whole window on its broom (`PetFlyby`, mounted in `App` so it
  plays whichever view ended the shift). It rides in from the left, hovers
  mid-screen with a bubble — *"Lähetään vittuun täst keilahallist"*, *"Jo oli
  aikakin"* or *"Nyt sitä kaljaa"* (`FRIDAY_LINES`) — and leaves to the right
  (6 s; clicks pass through). Meanwhile the Timer companion steps out (it
  puffs back in when the flight lands) and achievement cards wait their turn.
  Reduced motion shows it still, mid-screen, for 4.5 s. Off when the pet is.
- **After-shift bazooka (easter egg):** now and then (1 in 4,
  `BAZOOKA_CHANCE`) a saved shift makes an awake pet bring out a bazooka for a
  minute (`rollBazooka` in `petState.ts`), in the colours of the look being
  worn (`bazookaSprite`: neon for Neon, gold for the Gilded and Legend
  wizard). It is put away when the minute is up or the pose changes, e.g. a
  new shift starts, and never shows while the pet sleeps.
- **Guards:** loops run only when `motion === 'full'`; they pause with
  `animationsActive` (`animation-play-state: paused`); reduced motion shows the
  static pose and swaps it instantly.

### Placement

- Sits in the bigger of two free spots on the Timer card: the bottom-right
  corner under the controls, or beside the ring standing on its baseline
  (`petSpot` in `petState.ts`, re-run by a `ResizeObserver`). At most 1×; when
  it has to shrink it switches to smooth scaling so no pixels drop out, and
  under 64 px wide it hides. It never covers the ring, the dial or the buttons.
- `aria-hidden` for the sprite itself; the button around it is labelled e.g.
  *"Tähti, flying, energy 80%. Open pet"*.
- **Pet sheet** (`openSheet`): the current pose large with its name, rank
  and level with a progress bar to the next level, the energy bar with
  *"18.5 h of 30 h in the last 7 days"*, and lifetime hours. Naming and
  switching live only in Settings (since 2.1.2); the sheet points there with
  a *Pet settings* button.
- **One-time offer** (`PetHint.svelte`, added in 2.1.1 because people updating
  didn't find the setting): while the pet is off, a slim strip at the bottom of
  the Timer card offers the familiar or the wizard, or *No thanks*. Any answer
  sets `pet_hint_seen` and the strip never comes back; changing the pet in
  Settings sets it too. A toast then says where the setting lives. It waits
  while an unfinished shift needs a decision, drops to one row on windows
  700 px tall or less so the ring keeps its room, and, when answered from the
  keyboard, hands focus to the new pet (or START) as it goes. If the card has
  no room to place the pet (mid-size two-column windows), the toast says so
  instead of greeting a pet that isn't there. Its picture is only a preview:
  a click or right-click on it says once to pick a pet first (a 2.1.2 fix
  for "right-click does nothing").
- **Opening the sheet:** right-click, a long press or Enter. Since 2.1.2 a
  right-button release opens it too, for mouse and touchpad tools that
  swallow the `contextmenu` event (the guard keeps it to one sheet), and a
  sheet that fails to load says so in a toast instead of failing silently.

### Looks (done, 2.1.3)

Unlocked by pet level, picked on the pet sheet (*Looks*), stored as
`ui_prefs.pet_skin` (`petSkins.ts`, `storage.PET_SKINS`):

| Look | Level | Familiar | Wizard |
|---|---|---|---|
| Classic | 1 | the original | the original |
| Cosmic | 5 (80 h) | sunset wings in flight | sunset robe, tired |
| Neon | 10 (270 h) | highlighter bazooka, awake | highlighter bazooka, awake |
| Gilded | 20 (≈ 828 h) | sleeps in gold | gold awake, tired and asleep |
| Legend | 25 (≈ 1176 h) | sleeps as a golden dragon | gold with a gold bazooka, awake; gilded tired and asleep |

Each look redraws only some poses; the rest stay classic. Derive, don't
count: only the choice is stored, and the look drawn is the choice once its
level is reached, else classic (`activeSkin`), so deleting entries below a
level shows classic again until it is reached again. The last level drawn
is remembered (localStorage `weleho.petLevel`), so while the stats are still
loading on start a locked look never flashes. Reaching a look's level shows a
toast with *Wear it* (`newlyUnlockedSkins`; the first level seen after a start
is never news). It counts saved hours only, so the toast comes once the shift
is saved, never from a running or discarded one. Locked looks stay focusable
in the picker (`aria-disabled`), greyed out with the level that unlocks them;
Classic can always be picked, even while a locked choice is stored.

### Cosmetics (later)

Aura colours as a `drop-shadow` glow around the sprite, unlocked by
achievement tiers: bronze glow at 3 bronzes, silver, gold, and a legendary
flame aura for either Lulz achievement. Picked on the pet sheet; stored as
`pet_aura`. No new sprites needed.

### Setting storage

In `ui_prefs`, like `lulz` (`storage.UI_PREF_DEFAULTS`, `_check_setting`,
`types.ts`, `stores/settings.ts`):

- `pet`: `"off" | "familiar" | "wizard"` (default `"off"`)
- `pet_name`: string, trimmed, max 24 chars, `""` = default name
- `pet_hint_seen`: bool (default false), the one-time offer was answered
- `pet_skin`: `"classic" | "cosmic" | "neon" | "gilded" | "legend"` (default
  `"classic"`), the chosen look
- `pet_aura`: `"none" | "bronze" | "silver" | "gold" | "legendary"` (later)

`ui_prefs` only knows booleans and `target_hours` today, so this adds a small
validated-string branch.

## Data model changes

- One new optional top-level key in `data.json`: `achievements_seen`.
- New `ui_prefs` keys: `pet`, `pet_name`, `pet_hint_seen`, `pet_skin` (later `pet_aura`).
- No change to entries.

## Migration

- Clean on read with defaults for missing keys — the existing pattern; there is
  no schema version.
- Downgrade is safe **for top-level keys only**: `storage._load_raw` /
  `_save_raw` load and rewrite the whole dict, so an older version keeps
  unknown top-level keys untouched. Entries are different: up to 2.1.3,
  `storage._entry` raises `TypeError` on any entry key it doesn't know, which
  breaks the month view, Stats, achievements and the pet. Nothing here adds an
  entry key, but anything that does must wait for 2.1.4's tolerant reader
  ([V2_ACCURATE_PAY_PLAN.md](V2_ACCURATE_PAY_PLAN.md#214--groundwork-a-tolerant-entry-reader)).

## Net hours and per-date rates (2.2)

From 2.2 ([V2_ACCURATE_PAY_PLAN.md](V2_ACCURATE_PAY_PLAN.md#net-or-gross--who-counts-what)):

- Hour, target-day and streak badges and the pet (`pet_stats`: lifetime and
  8-week days) count **net** minutes (gross minus the shift's break).
- Badges about the clock — overnight, early bird, night owl, marathon,
  inferno, blue flame — stay **gross**: they are about when and how long you
  were there.
- Earnings badges sum net hours × the rate in effect on each shift's date
  (`evaluate` takes a rate callable instead of one `pay_rate`), so a raise no
  longer rewrites past earnings.
- Badges already seen stay unlocked (`with_seen`), so starting to log breaks
  never takes one away.

## Sync interaction

`achievements_seen` and the `pet*` prefs belong in the *synced settings* list of
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
  level curve and rank titles, pose selection (target crossing, the 22:00 and
  06:00 edges, the holiday rule).
- `frontend/tests/petUi.test.ts` — companion placement (`petSpot`), label,
  petting vs opening the sheet, the sheet's way to Settings, tired sighs (timing,
  petting, hushing at the end of the shift, stepping out for the fly-by) and
  the Friday fly-by (Friday, past midnight, other days, pet off).
- `frontend/tests/petLogic.test.ts` also covers the line helpers
  (`tiredLines`, `fridayShift`, `pickLine`).
- `frontend/tests/petSprite.test.ts` — the animation layers: seams, still
  boxes (on the art grid, clear of the particles, covered by the lower
  layer's islands), particle clips and phases, the plain picture without
  motion. The `STILL` boxes are hand-picked from the art, so check them when
  the idle sprites change.
- `tests/test_pet_particles.py` — `petParticles.ts` matches the art, and the
  sleepy poses keep their z's.
- `frontend/tests/petSkins.test.ts` — the looks match `storage.PET_SKINS`,
  unlock levels, which sprite each look and the bazooka draw, and every look
  sprite's size, seam and particles against the art (the WebP header is read
  directly), overhangs on whole art pixels.
- `frontend/tests/petUi.test.ts` also covers the looks picker (locked, wear),
  the unlock toast, a locked choice drawn classic, and the bazooka (chance,
  one minute, awake only, put away when a shift starts).
- `tests/test_storage.py` — `pet` / `pet_name` / `pet_skin` validation and defaults.
- In the browser mock, `?pet=wizard&petxp=1200&skin=neon` starts with that
  pet, 1200 extra lifetime hours and that look.

## Implementation order

1. `achievements.py` engine and tests.
2. API, `achievements_seen` persistence and first-run backfill.
3. Stats tile, `AchievementsSheet`, unlock toasts (+ Lulz flare).
4. ~~Art pass~~ — done: sprites in `frontend/src/assets/pets/`.
5. ~~Pet logic as a pure module (`petLogic.ts`: energy, level, rank, pose) with tests.~~ — done
6. ~~`pet` / `pet_name` prefs, Settings control.~~ — done
7. ~~Pet companion on the Timer card (poses, loops, reactions, petting) and the pet sheet.~~ — done
8. ~~Looks unlocked by pet level, and the after-shift bazooka.~~ — done (2.1.3)
9. Cosmetics (auras) unlocked by achievements.
