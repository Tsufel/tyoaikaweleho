# Improvement sweep — plan

Branch `feat/go-crazy-improvements` (off `ui-overhaul` at 3ed7221). This is a time-boxed
(3 h) "think of everything" sweep. Eight parallel code readers each mapped one
area and proposed concrete, file-cited improvements. The full catalogue (126
ideas) is at the bottom. Ideas are carried out in rounds. Each round is a set of
workstreams that own mostly separate files, so they can be built in parallel
and merged.

Rules for every workstream:

- **User data is sacred.** No change may risk losing `data.json`,
  backups or `shifts.txt` content. Storage changes come with tests.
- **API changes go end to end:** `webapp/controller.py` → `webapp/api.py` →
  `frontend/src/lib/api/types.ts` → `frontend/src/lib/api/mock.ts` →
  `docs/V2_UI_API.md`, plus `tests/test_api_contract.py`.
- **Don't touch the owner's uncommitted chart work:** `frontend/src/charts/*`,
  `views/stats/KpiTile.svelte`, `views/stats/StatsView.svelte`,
  `frontend/tests/stats.charts.test.ts`.
- Gates: `pytest tests/`, `npm run check` (no warnings), `npm test`,
  `npm run build`.

## Round 1

| Stream | Theme | Ideas (catalogue #) |
|---|---|---|
| A | Data safety in storage | 1, 68 (no data.json rewrite on launch or Review; `get_recovery`), 34+66 (ANSI/BOM `shifts.txt`), 35 (append after a Notepad edit), 48 (case-insensitive de-dupe), 67 (tmp cleanup + retry on lock), 77 (clean shift names), 39 (import = one save + snapshot), 71 (safety copy before an update install), 73 (crash log + rotation) |
| B | Timer flows | 2 (Stop at…), 3 (adjust the running shift's start/job), 5 (recovery validation), 6 (stale recovery Escape), 7 (stuck recovery_pending), 8 (24 h saved as 0 min), 11 (ETA/overtime line), 12 (shift receipt toast), 13 (mock discard parity), 119 (this-week progress), 113 (elapsed time in the window title) |
| C | Entries UX | 19+122 (duplicate shift, Ctrl+D), 20 (row context menu), 21 (empty state), 22 (filter by job + totals), 23 (richer footer), 25 (discard-changes guard), 26 (date hints), 28 (grid semantics), 29 (row polish), 30 (copy month as text), 112 (default end from the daily target), 24 (overlap → which shift) |
| D | Excel export/import | 36 (text times/decimal hours), 37 (EAS week order at year end), 38 (re-import own exports), 45 (better empty-import summary), 47 (nicer Simple export), 44 (CSV export of a date range), 115 (names on the EAS sheet) |
| E | Shell, keyboard, a11y | 50 (modal focus restore), 51 (lazy chunk retry), 52 (sticky toasts survive the cap), 53 (pause toasts when hidden), 63 (collapse duplicate toasts), 54+123 (shortcut cheat sheet ?/F1), 55 (Ctrl+1/2/3 views), 57 (popover focus-out), 59 (route focus), 61 (tooltip hide), 65 (menu typeahead), 58 (forced-colors), 64 (skippable intro + Konami) |
| F | Stats, achievements, pet | 81 (drowsy text), 82 (zero-length shifts in stats), 84+85+120 (personal records + Hall of fame), 87 (streak chip), 88 (more milestones), 89 (calendar Easter-egg badges), 90 (next-up strip), 91 (pay-rate 0 hint), 92 (sheet a11y), 93 (pet chatter), 86 (weekly recap) |
| G | Settings & your data | 41 (shift list refresh), 43+116 (Your data card: open folder, backup status, back up now), 78 (restore a snapshot, safety copy first), 70+42 (weekly/monthly retention, never prune user files), 46 (pay preview polish), 74 (plain-language update errors), 75 (re-check updates every 24 h) |
| H | Dev experience & tests | 100 (ruff), 101 (pytest/coverage config), 102 (CI hardening), 103 (smoke test in CI), 104 (faster vitest), 105 (bridge/flow/shortcuts tests), 106 (mock conformance), 107 (risky-path tests), 108 (repo safety nets), 97+98 (shape/literal contract tests), 109 (README/dev guide) |

## Round 2 (after reviewing round 1)

Round 2 is picked once round 1 is merged and reviewed. It starts with a code
review of the merged diff and its fixes, then takes the most valuable
leftovers. Candidates: 10 (still-working nudge), 114 (per-shift notes),
117+118 (Finnish holidays), 4 (DST), 14 (stop time at press), 15 (recent-job
chips), 18 (undo edits), 31/72 (parse once), 69 (missing data.json with
backups), 99 (release hygiene), 124/125/126 (fun), 62 (UI zoom), 56 (command
palette), 94 (work anniversary).

## Progress log

- Round 1: done and merged (A to H). 85 ideas shipped:
  - A data safety: 1, 68, 34, 66, 35, 48, 67, 77, 39, 71, 73
  - B timer: 5, 7, 8, 6, 2, 3, 11, 12, 13, 113 (119 skipped: it needs this
    week's minutes on the timer side, so it moved to round 2)
  - C entries: 112, 21, 23, 29, 19, 122, 22, 30, 25, 26, 20, 28, 24
  - D Excel: 36, 37, 38, 45, 47, 44, 115
  - E shell / a11y: 50, 52, 51, 53, 63, 54, 123, 55, 57, 59, 61, 65, 64, 58
  - F gamification: 81, 82, 84, 85, 120, 87, 88, 89, 90, 91, 92, 93, 86
  - G settings / your data (landed late): 43, 116, 78, 70, 42. That covers the
    Your data card, the backups list with restore (a safety copy is made
    first) and weekly/monthly snapshot retention. 41, 46, 74 and 75 moved to
    round 3.
  - H devex: 108, 100, 101, 102, 103, 104, 105, 106, 107, 97, 98, 109

  After the merge: 867 pytest, 766 vitest, ruff clean, svelte-check 0 errors,
  and the Vite build passes. ui-overhaul (the owner's chart work) is merged in.
- Round 2: done and merged. 17 ideas shipped plus 3 bug fixes:
  - timer: 14 (the stop time is the minute STOP was pressed), 4 (DST-safe
    elapsed time), 10 (the "Still working?" banner, in-app part only), 15
    (recent-job chips), 119 (the "This week" line). The taskbar flash was
    skipped.
  - entries: 114 (per-shift notes), 18 (undo for edits and adds, using
    revert_entry with a stale guard).
  - holidays: 117 (Finnish public holidays, with Python and TS twins tested
    against one golden file), 118 (holidays never break a streak), 125
    (contextual idle greeting). 94, 124 and 126 were skipped for time.
  - devex: 31/72 (data.json is parsed once per API call; bootstrap went from
    15 loads to 1), 99 (bump_version.py, plus release notes taken from
    changelog.py).
  - shell: 62 (UI zoom with Ctrl +/-/0, 80 to 150 %), 56 (command palette,
    Ctrl+K).
  - 69 (done here): a missing data.json is restored from the newest backup
    and the notice says "was missing".
  - backend review fixed 3 bugs. timer_adjust now cleans the job name. Excel
    writes job names as text, so "=Boss" is no longer a formula. Imported
    shift names are cleaned. The frontend reviewer could not start (its
    worktree was broken), so it is re-run in round 3.

  After the merge: 1100 pytest, 819 vitest, ruff clean, svelte-check 0 errors,
  and the build passes.
- Round 3: _done_. Five 20-minute streams, all merged without conflicts:
  - Frontend bug hunt: an older ui_prefs reply no longer rolls back a newer
    change (holding Ctrl+= lost zoom steps).
  - Zoom audit: the pet, the chart hover and the right-click row menu use
    layout px (`layoutPoint`).
  - Notes column (F) in the Full Excel export, written as text, plus a
    high pay-rate warning above 200 €/h (46).
  - The shown month reloads on focus, at most every 5 s and never while a
    modal is open or you're typing (41). Editing a shift with a legacy job
    name no longer fails when the name wasn't changed.
  - Clearer update-check errors (offline, timeout, rate limit, server
    error), and an automatic re-check every 24 h while the app is open
    (74, 75).
  - Done inline: a Lulz tooltip on the earnings with a fun equivalent
    (124).
  - Gates after the merge: 1128 pytest, 832 vitest, svelte-check, ruff and
    build all green.
- Round 3 review: three read-only reviewers looked at the round-3 diff.
  They found one real bug: when overlapping ui_prefs saves failed or
  replied out of order, the screen could keep a value that was never
  saved. The store now settles on the newest state Python confirmed.
- Round 4 (inline, in the last minutes):
  - The palette's `aria-expanded` follows whether anything matches.
  - "Filter the month" is offered only when there is a filter box.

## Idea catalogue

### timer

- **#1 Review link and recovery_pending START re-run the whole bootstrap, which rewrites data.json** — bug, S, value high, risk low. Pointless data.json writes wear away the .bak safety net, and a data-repair notice can be silently lost. User data safety comes first.
- **#2 'Stop at…' to fix a forgotten timer: save the shift with a chosen end time** — feature, M, value high, risk low. Forgetting to stop is the most common time-tracking failure. The fix is now one action and doesn't need a later table edit that is easy to forget.
- **#3 Adjust the start time (and job) of the running shift** — feature, M, value high, risk medium. It covers 'forgot to start, started at 08:45 really' and 'picked the wrong job' without discarding a running shift.
- **#4 DST fall-back can silently discard a real shift (naive elapsed time)** — bug, M, value medium, risk medium. Night-shift workers can lose a real shift or get a wrong ~24h entry once a year. Rare, but it's a silent data-correctness bug.
- **#5 Recovery Save accepts zero-length and 23h entries without a word** — bug, S, value high, risk low. Crash recovery is exactly when people type an end time from memory, and a typo leads straight to a wrong timesheet.
- **#6 Stale recovery: don't make Escape or autofocus resume a days-old shift** — ux, S, value medium, risk low. The likely right action for an old crash is 'save it with an end time', not 'keep it running'.
- **#7 recovery_pending stays stuck after a saved shift whose session.json couldn't be removed** — bug, S, value medium, risk low. A phantom 'unfinished shift' warning and a START that doesn't work are confusing, right after the app has just written data.
- **#8 A ~24h shift can be saved as 0 minutes (seconds vs HH:MM mismatch)** — bug, S, value low, risk low. A full day of work silently becomes 0h. It's a narrow window, but the fix is a one-liner with a test.
- **#9 Show elapsed time in the window title / taskbar while running** — feature, S, value medium, risk low. It shows in Alt-Tab and the taskbar that the timer is running, a cheap first step toward 'never forget the timer' (BACKLOG 2.4).
- **#10 'Still working?' nudge: flash the taskbar and show an in-app banner past target + N hours** — feature, M, value high, risk low. It's the biggest piece of BACKLOG 2.4 that doesn't need the tray or the 2.2 break model, and it directly prevents 14h phantom shifts.
- **#11 Target ETA and overtime line under the running clock** — ux, S, value medium, risk low. 'When can I leave?' is the question people open a timer app to answer, and screen-reader users currently get no target event.
- **#12 Shift receipt: show earnings (and a pet quip) in the 'Shift saved' toast** — fun, S, value medium, risk low. It's a cheap moment of reward that fits the app's gamified tone, and it shows the money number people care about.
- **#13 Mock timer_discard disagrees with Python when idle** — tests, S, value low, risk low. The mock drives dev mode and the vitest suite, so differences hide real UI paths (e.g. the not_running toast in stopShift/discard).
- **#14 Stop time = when STOP was pressed, not when the confirm was answered** — ux, M, value medium, risk medium. Timesheets should reflect the moment the user decided to stop, not when they returned to the dialog.
- **#15 Recent-job chips under the idle Job/shift combobox** — ux, M, value medium, risk low. It makes starting the right job one click, and fewer wrong-job entries need editing later.
- **#16 Remove dead WorkTimer helpers (elapsed_str, elapsed_seconds, start_time_str)** — devex, S, value low, risk low. Less surface area, and it removes a second, untestable source of truth for elapsed time.
- **#17 Pause / break button (after 2.2 breaks land)** — feature, L, value medium, risk medium. Lunch breaks are the main reason people stop and restart the timer, or forget to subtract, which skews pay.

### entries

- **#18 Undo for edits and adds, not just deletes** — feature, M, value high, risk medium. Inline cell editing is one click away from a typo; delete is the only reversible action, which is backwards (edits are far more common). Fingerprint guard keeps data safety.
- **#19 Duplicate shift (Ctrl+D) and 'same as last shift' defaults** — feature, S, value high, risk low. Most part-timers repeat the same shift pattern; re-typing job and times every time is the main friction of manual entry.
- **#20 Right-click context menu on shift rows** — ux, S, value medium, risk low. Desktop users expect right-click on a table row; it makes Duplicate/Copy discoverable without a crowded footer.
- **#21 Empty state: month-aware text and action buttons** — ux, S, value medium, risk low. Verified: the copy is wrong for non-current months, and the empty state is a dead end with no clickable action.
- **#22 Filter shifts by job with filtered totals (Ctrl+F)** — feature, M, value high, risk low. People with several jobs need per-job hours for different timesheets/employers; today they'd add it up by hand.
- **#23 Richer footer: shift count, days worked, average** — ux, S, value medium, risk low. Cheap and answers the questions people actually have at month end ('how many days did I work?').
- **#24 Overlap icon tells which shift and jumps to it** — ux, M, value medium, risk low. An overlap is usually a double-logged shift; finding the twin in a long month is tedious.
- **#25 EntryModal: confirm before discarding typed changes, skip no-op saves** — robustness, S, value medium, risk low. Verified both by reading: Esc throws away a half-filled form, and an unchanged Save still does a full write + backup rotation (needless churn on the user's data file).
- **#26 EntryModal soft date hints (other month, far future/past)** — ux, S, value medium, risk low. Typoed years create entries that vanish from the current view; a hint catches it before save without blocking legit backdating.
- **#27 Better delete/restore toast copy** — ux, S, value low, risk low. Verified grammar glitch in a toast users see on every delete.
- **#28 Proper grid semantics for the shifts table** — a11y, S, value medium, risk low. Keyboard nav is already good; the a11y tree doesn't reflect it.
- **#29 Row polish: today highlight, weekend tint, shorter dates, partial-week label** — ux, S, value medium, risk low. Makes a long month scannable at a glance and removes a misleading week total.
- **#30 Copy month (or selected shift) as text to clipboard** — feature, S, value medium, risk low. People paste hours into Slack/email to a manager; Excel export is overkill for a quick check-in.
- **#31 list_month reads and parses data.json three times** — perf, S, value low, risk low. Verified by reading: 3 full parses per refresh; years of history make each refresh slower and widen the window for a locked-file error mid-refresh.
- **#32 Multi-select with bulk delete and single undo** — feature, L, value medium, risk medium. Cleaning up a bad import or a duplicated week means many single deletes, each with a confirm dialog.
- **#33 Fix misleading inline-editor test name** — tests, S, value low, risk low. The test name documents a behaviour the code does not have, which will mislead the next person touching the editor.

### settings-export

- **#34 shifts.txt saved as ANSI in Notepad stops the app from starting** — bug, S, value high, risk low. Clicking a button the app itself offers can leave the app unable to start. This is the worst bug found in this area.
- **#35 Adding a shift after a Notepad edit glues it onto the last line** — bug, S, value high, risk low. The app sends people to edit shifts.txt in Notepad, and the next 'Add a shift' then quietly corrupts their shift names.
- **#36 Excel import misreads text times like '8:30' and decimal hours, and stores invalid times** — bug, S, value high, risk low. Imports silently drop or corrupt rows, and impossible times end up in the user's data file.
- **#37 Full (EAS) export orders weeks wrong at the year boundary** — bug, S, value high, risk low. Every December and many Januaries the timesheet sent to the manager comes out in the wrong order.
- **#38 The app can't re-import its own exports (Full gives 0 rows, Simple loses shifts)** — bug, M, value high, risk low. Exports are the only backup most users ever look at, and today they can't be read back in without losing data.
- **#39 Excel import: one save per row and no safety snapshot first** — robustness, M, value high, risk low. Faster and atomic imports, plus a real restore point before the riskiest bulk change the app makes.
- **#40 'Undo import' action on the import result** — feature, M, value medium, risk low. Picking the wrong file today adds dozens of rows that have to be deleted one by one.
- **#41 The shift list doesn't refresh after editing shifts.txt** — ux, S, value medium, risk low. The Settings button for editing shifts looks broken, because changes don't show up.
- **#42 Daily-snapshot pruning can delete a user's own copy in backups/** — robustness, S, value medium, risk low. Backups are meant to be untouchable, and today the cleanup can remove files it didn't create.
- **#43 Settings 'Your data' card: open data folder, backup status, back up now** — feature, M, value high, risk low. Users can't find their data or tell whether backups exist without digging through the install folder.
- **#44 CSV export of any date range (Finnish-Excel friendly)** — feature, L, value high, risk low. Tax returns and quarterly reports currently take 3 to 12 separate exports.
- **#45 Import summary should say why nothing was found, and drop the .xls filter** — ux, S, value medium, risk low. Imports that do nothing currently fail without any explanation.
- **#46 Settings polish: 'Include pay' and the pay preview** — ux, S, value low, risk low. Small inconsistencies in the most-used settings card.
- **#47 Nicer Simple export: frozen header, weekly subtotals, workbook metadata** — feature, S, value low, risk low. Makes the monthly sheet easier to check before sending it, at almost no risk.
- **#48 Case-insensitive de-dupe in the shift list** — bug, S, value low, risk low. Shift lists that look the same get duplicated, which confuses the pickers and stats grouping.
- **#49 Fun: an 'Exporter' achievement and a pet reaction on export** — fun, M, value low, risk low. Ties the monthly chore into the existing gamification.

### shell-a11y

- **#50 Fix focus restore after a modal closes (the shell is still inert when Modal calls focus)** — bug, S, value high, risk low. Keyboard users lose their place after every confirm. The next Delete/Enter shortcut then does nothing, because inTable gating needs focus inside the table.
- **#51 Add {:catch} with Retry to the lazy Stats and Lulz FX chunk imports** — robustness, S, value medium, risk low. Without a catch branch, a broken install shows a blank page and gives the user nothing to try.
- **#52 Keep sticky toasts (ms:0) when the 4-toast cap trims the stack** — bug, S, value high, risk low. Toasts about data safety should not be evicted by other toasts.
- **#53 Pause toast countdowns while the window is hidden or unfocused** — ux, S, value medium, risk low. Today the Undo toast can expire while the user is in another window, so they never get a chance to use it.
- **#54 Keyboard cheat sheet on ? / F1, with one shared source of truth for shortcuts** — feature, M, value high, risk low. The shortcuts are hard to discover; today they are listed only at the bottom of Settings.
- **#55 View switching shortcuts: Ctrl+1/2/3, and Esc on Stats goes back** — feature, S, value medium, risk low. Gives keyboard users parity for navigating the app. It is cheap to add.
- **#56 Command palette (Ctrl+K)** — feature, L, value medium, risk low. The power-user feature for a 'go crazy' pass. It also makes toggles that are buried in Settings reachable from anywhere.
- **#57 Close popovers when focus leaves them (Tab out of the month picker)** — a11y, S, value medium, risk low. Without this, keyboard users are left with a stray popover and focus that jumps unpredictably.
- **#58 Windows High Contrast (forced-colors) support** — a11y, M, value medium, risk low. The app already detects high contrast but only uses that to turn glass off; this makes it usable in Windows High Contrast.
- **#59 Move focus and announce on route change (Settings / Stats / main)** — a11y, S, value medium, risk low. After a route change, screen-reader and keyboard users currently have to start again from the top of the page.
- **#60 Hide or disable topbar controls while boot failed or is loading, and make the error card more useful** — ux, S, value medium, risk low. When boot fails, the user should get clear next steps instead of controls that silently do nothing.
- **#61 Hide the tooltip on scroll, resize and window blur** — bug, S, value low, risk low. Fixes tooltips that are visibly left behind in the wrong place.
- **#62 In-app UI zoom (Ctrl+= / Ctrl+- / Ctrl+0) persisted in ui_prefs** — a11y, L, value medium, risk medium. The UI cannot be enlarged at all today because browser zoom is blocked.
- **#63 Collapse duplicate toasts into one with a ×N counter** — ux, S, value low, risk low. Stops duplicate toasts from filling the stack and pushing out the ones that matter.
- **#64 Skippable intro, plus a Konami-code easter egg** — fun, S, value low, risk low. It matches the app's playful tone and lets impatient users skip the splash.
- **#65 Typeahead in Menu, and Home/End in Combobox** — a11y, S, value low, risk low. Brings these widgets in line with the WAI-ARIA keyboard patterns.

### backend-robustness

- **#66 An ANSI-encoded shifts.txt stops the app from starting; a BOM adds a junk character to the first shift** — bug, S, value high, risk low. Finnish users edit shifts.txt by hand ('Open shifts file' button), and Notepad, Excel and older editors often save ANSI or a BOM. One 'ä' currently stops the app from starting, with only a cryptic 'Unexpected error'.
- **#67 _save_raw leaves a partial data.json.tmp and reports 'internal' on unencodable text; no retry when Windows briefly locks data.json** — robustness, S, value high, risk low. Atomic writes are the core of data safety. Today a failed save leaves debris, and a few hundred milliseconds of antivirus lock becomes a user-visible 'could not be saved'.
- **#68 Every launch rewrites data.json and overwrites .bak with an identical copy, so the 'one save ago' backup is lost** — bug, S, value high, risk low. It keeps .bak meaningful, it is the first recovery candidate in _backup_candidates, and it avoids a pointless fsync on every start.
- **#69 If data.json goes missing while backups exist, the app starts empty and its later saves gradually overwrite the backups** — robustness, M, value high, risk medium. This is the most likely way a real user loses months of hours without the app saying anything, and the backups that could save them are already on disk.
- **#70 Keep weekly and monthly snapshots, not just the 14 newest daily ones** — robustness, S, value high, risk low. It costs a few hundred KB of disk and adds a year of recovery points for slow-to-notice mistakes.
- **#71 Take a safety copy of user data before running the installer for an update** — robustness, S, value high, risk low. Updates are the riskiest moment for user data, and one extra copy is cheap.
- **#72 Parse data.json once per API call, not up to 15 times** — perf, M, value medium, risk medium. Startup and month navigation get noticeably faster for long-time users, whose data keeps growing, and the change does not touch the file format.
- **#73 Log uncaught and native crashes to disk, and rotate error.log cleanly** — robustness, S, value medium, risk low. When a user reports 'it just closed', there is currently nothing to look at.
- **#74 Explain update-check failures in plain language (offline, GitHub rate limit, timeout)** — ux, S, value medium, risk low. Update failures are the most common network message users see, and the current text means nothing to a shift worker.
- **#75 Check for updates again every 24 hours while the app stays open** — feature, S, value medium, risk low. It gets security and data-safety fixes to long-running installs.
- **#76 Let the user close the window even if the frontend never answers close:requested** — robustness, S, value medium, risk medium. A window you can't close is a bad failure mode, and the running shift is already safe in session.json.
- **#77 Clean shift names at the API boundary (newlines, control characters, lone surrogates, length, wrong types)** — bug, M, value medium, risk low. It closes real (small) data-corruption paths and turns 'Unexpected error' into field-level messages.
- **#78 Backups panel in Settings: list snapshots, restore one (with a safety copy first), open the data folder** — feature, L, value high, risk medium. It turns the existing backup work into something users can actually use, and the restore itself is backed up first.
- **#79 Refuse to install the OCR DLC when there is no published checksum** — robustness, S, value medium, risk medium. The DLC and the app installer should follow the same rule for running downloaded code.
- **#80 Accept two-digit years in dates ('2.6.26')** — ux, S, value medium, risk low. A small change that matches how users type dates; it also affects OCR and import paths that use parse_date_input.

### stats-gamification

- **#81 Fix the pet sheet's drowsy mood text: it says 'past today's target' at 75%** — bug, S, value medium, risk low. The user sees UI text that contradicts what is actually happening. It is a one-line fix with an obvious payoff.
- **#82 Stats counts zero-length entries as shifts and can show a 0-minute 'Longest shift'** — bug, S, value medium, risk low. The KPI tiles should agree with each other and with the achievements engine. 'Longest shift: 0 min' looks broken.
- **#83 Mock get_stats parity: open entries, longest tie-break, by_shift order** — robustness, S, value low, risk low. The browser mock drives UI dev and the vitest UI tests. Silent divergence hides bugs that only appear in the real app.
- **#84 Personal records engine + get_records API** — feature, M, value high, risk low. This is the backlog's top parking-lot idea and it feeds several UI ideas: a records panel, the weekly recap, a streak chip. It is pure and easy to test.
- **#85 'Hall of fame' records panel inside the Achievements sheet** — feature, M, value high, risk low. Delivers personal records without touching the WIP Stats files. Records are the second half of 'collecting' and make the sheet worth opening even when no new badge has unlocked.
- **#86 Weekly recap card on the first open of a new week** — feature, M, value high, risk low. A tiny weekly reward moment that needs no backend change. It reuses get_stats and ranges.ts as they are.
- **#87 Current workday streak chip on the pet sheet (no backend change)** — feature, S, value medium, risk low. Streaks motivate. Doing it in petLogic avoids the WIP KpiTile while still putting the streak where the user looks every day.
- **#88 More milestone achievements, reusing existing medal art via an optional `icon` key** — feature, M, value medium, risk low. Long-term users run out of goals between 500 h and 1000 h. More mid-tier goals keep the collection loop alive.
- **#89 Hidden calendar Easter-egg achievements (Friday the 13th, Christmas shift, 13:37, double header, seven-day week)** — fun, M, value medium, risk low. The owner asked for fun with 'no idea too stupid', and the app already has Lulz and Friday fly-by humour. Hidden calendar badges are cheap and make people smile when they unlock.
- **#90 Achievements sheet: 'Next up' strip with the closest locked badge** — ux, S, value medium, risk low. Gives the user a concrete next goal right away instead of a wall of 17 cards.
- **#91 Earnings badges: explain how to start them when the pay rate is 0** — ux, S, value medium, risk low. A progress bar that can never move feels broken. One line of guidance fixes that.
- **#92 Achievements sheet a11y: locked/unlocked state and progress semantics** — a11y, S, value medium, risk low. The app already does a11y carefully (focus return, live regions), and this sheet is the gap.
- **#93 Pet chatter: happy time-of-day lines when petted, plus a tickle combo** — fun, S, value medium, risk low. Makes the pet feel alive between shifts, fits the Finnish-flavoured humour already in TIRED_LINES and FRIDAY_LINES, and is pure frontend.
- **#94 Pet 'työvuosipäivä': anniversary of the first shift** — fun, M, value medium, risk low. A personal touch that rewards long-term use. It needs only a small additive contract change.
- **#95 Test gaps: stats.summarize edge cases and pet_stats window** — tests, S, value medium, risk low. Cheap guardrails before the records and new-achievement work changes this code.
- **#96 Tool achievements v2 via an add-only event counter (careful storage change)** — feature, L, value medium, risk medium. Completes the gamification plan's deferred v2. It is the only idea here that touches stored data, so it is scoped to an add-only key.

### devex

- **#97 Contract test for shape keys: types.ts interfaces vs real Python payloads (+ fix 2 verified doc drifts)** — tests, M, value high, risk low. The only existing contract test (test_public_methods_match_types_ts) checks method names only; payload key drift between Python, types.ts and the doc already happened twice (data_recovery, pet_skin) without anything failing.
- **#98 Literal contract test: event names, data:changed reasons, error codes, confirm kinds/options vs types.ts unions** — tests, M, value high, risk low. These strings cross the language boundary untyped; a typo in a Python emit or a new error code silently does nothing in the UI. Today only method names are checked.
- **#99 Release hygiene test + version bump script + release notes from changelog.py** — devex, M, value high, risk low. Cutting a release currently means hand-editing 4 files in sync and the GitHub release body is just auto-generated commit titles, while good user-facing notes already exist in changelog.py.
- **#100 Add ruff (pyflakes-level) lint and fix the 11 current findings** — devex, S, value medium, risk low. There is no Python linting at all; pyflakes-level rules catch undefined names and dead code cheaply and the current baseline is tiny, so it can be made zero and enforced.
- **#101 pytest/coverage config in pyproject.toml with a coverage floor** — tests, S, value medium, risk low. Coverage is printed but never enforced and is skewed by including tests/*; no shared pytest config exists (no pyproject/pytest.ini/setup.cfg).
- **#102 CI hardening: least-privilege token, concurrency, timeouts, pinned PyInstaller, Dependabot** — robustness, S, value medium, risk low. Reproducible release builds and cheaper CI; currently the release toolchain floats while the app deps are carefully pinned (pywebview==6.2.1, exact npm versions).
- **#103 Run the --smoke-test from source in every CI run, not only at release time** — tests, M, value high, risk low. Today a bootstrap/window/JS-load regression is only caught after tagging, inside the release job; catching it on the branch push is far cheaper. Unit tests cover webapp/app.py at only 26%.
- **#104 Halve vitest runtime: don't create jsdom for pure-logic test files; tighten frontend tooling** — perf, M, value medium, risk low. Faster local feedback loop and CI; pure modules also become safer against accidental DOM coupling.
- **#105 Unit tests for the untested frontend foundation: bridge.ts, flow.ts, shortcuts.ts** — tests, M, value high, risk low. These are the seams every view depends on (API calls, confirm protocol, all keyboard shortcuts) yet have zero direct coverage; regressions would be app-wide.
- **#106 Mock API conformance smoke test (mock.ts is 1150 lines with no tests)** — tests, S, value medium, risk low. The browser mock is the main design/dev tool (`?mock`), and drift from Python behaviour misleads UI work; TS only checks signatures, not envelopes or flag behaviour.
- **#107 Python tests for uncovered risky paths: startup background checks, EventBus failures, temp-installer cleanup, DLC write failure** — tests, M, value medium, risk low. These are the paths that run unattended (background threads, cleanup that deletes files) where a bug is invisible until a user hits it.
- **#108 Repo safety nets: conftest guards for network/DLC, .gitignore for damaged-data copies, .gitattributes for CRLF batch files** — robustness, S, value high, risk low. User data must never be committed, tests must never touch the network or tracked files, and the documented `run.bat` path must work for every clone.
- **#109 Refresh README + add a developer guide (verified drift list)** — docs, M, value medium, risk low. New contributors (and future agent runs) rely on README/docs; several statements are now false and useful dev affordances are undiscoverable.
- **#110 run.bat/build.bat: detect stale Python deps, add a dev launcher, checksum + no tracked-file rewrites** — devex, S, value medium, risk low. Removes the most common 'works on CI, broken locally' traps and makes the safe dev setup the default one.
- **#111 Source runs: DLC install/remove rewrites the tracked repo-root image_ocr.py** — bug, M, value medium, risk medium. A developer clicking through the DLC UI silently modifies/deletes repo source and can commit it by accident; a scratch data dir is supposed to make dev runs side-effect free.

### wild

- **#112 New-entry default end time ignores the Daily target setting** — bug, S, value medium, risk low. This is a real, daily papercut in the most common manual flow, and the fix is one line.
- **#113 Running timer in the taskbar title, driven from Python (2.4 slice)** — feature, M, value high, risk low. This is the cheapest standalone part of '2.4 Never forget the timer'. Users see the shift is still running from the taskbar or Alt+Tab without opening the app, and it needs no tray icon.
- **#114 Per-shift notes (2.2 slice that can ship alone)** — feature, M, value high, risk medium. The plan names notes as a 2.2 goal ('covered for Mia'). People keep a second list today, and the groundwork for this is already in place.
- **#115 Your and your manager's names on the EAS sheet (2.3 step 1)** — feature, S, value high, risk low. This is the smallest and most visible part of the 2.3 plan, and it removes a monthly manual step.
- **#116 Read-only backups list and 'Open data folder' in Settings (2.3 restore, first slice)** — robustness, M, value medium, risk low. Trust in backups is the core of 'user data safety is sacred', and this ships the safe half of the restore feature first.
- **#117 Finnish public holidays, computed locally (2.6 slice)** — feature, M, value medium, risk low. It is a prerequisite for the saldo, streak and pet rules in 2.6, it is useful by itself (why nobody worked on 6 Dec), and it is pure, easy to test code.
- **#118 Public holidays never break the 5-day streak (2.6 slice)** — bug, S, value medium, risk low. The backlog says 'holidays never break streaks'. This is that rule at about 10 lines once the holiday module exists.
- **#119 'This week' progress line on the Timer card (2.6 time-balance slice)** — feature, S, value high, risk low. Shift workers constantly ask 'how much more this week?'. This answers it with data that is already fetched and no new API, as a first step toward the saldo.
- **#120 Personal records section in the Achievements sheet** — feature, M, value medium, risk low. It feeds the gamification loop by giving users something to beat, and it fits the existing sheet without touching the Stats WIP files.
- **#121 Weekly recap toast on the first open of a new week** — feature, M, value medium, risk low. It gives a little dopamine and a check that last week's hours look right before the timesheet is due.
- **#122 Duplicate shift (Ctrl+D) and 'same as last time' prefill** — ux, S, value medium, risk low. Shift workers often enter a run of identical shifts after the fact (e.g. from a paper roster), and this turns 4 fields × N into one keystroke each.
- **#123 Keyboard shortcut cheat sheet on '?' / F1** — a11y, S, value medium, risk low. Users discover F5/PgUp/Ctrl+Z without reading the README, keyboard-only users benefit, and it is quick to build.
- **#124 'What you've earned so far' equivalents under the live earnings** — fun, S, value low, risk low. It matches the playful tone (pet, Lulz, Finnish pet lines) and makes long shifts feel rewarding, at almost no cost.
- **#125 Contextual idle greeting instead of the static 'Press START (F5)…'** — ux, S, value low, risk low. The app opens to this line every shift, and a small human touch fits the app's personality.
- **#126 Seasonal touches plus a Konami-code Easter egg** — fun, M, value medium, risk low. The owner asked for silly delight. Seasonal surprises make a daily-use tool feel alive, and the opt-out plus reduced-motion checks keep it respectful.
