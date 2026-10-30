import { get, writable } from 'svelte/store';
import { api } from '../api/bridge';
import type { Achievement, AchievementTier, AchievementsData, TimerState } from '../api/types';
import { openSheet } from './confirm';
import { month } from './entries';
import { settings } from './settings';
import { timer } from './timer';
import { toast } from './toasts';

// Achievements are derived from the entries by Python (achievements.py), so
// instead of hooking every save/edit/delete/import path this re-asks whenever
// the viewed month is re-read (every one of those paths ends in refreshMonth)
// or the settings change (target hours, pay rate). Unlocks are celebrated by
// AchievementUnlock (mounted in App), which acknowledges each one as it shows it,
// so closing the app before a card appears celebrates it again next launch.
// Nothing is celebrated while a shift runs (or waits to be recovered): those
// unlocks stay unacknowledged (Python keeps listing them as new) until the
// shift ends, and the check that follows pops them up.

export const achievements = writable<AchievementsData | null>(null);
/** Waiting to be celebrated, oldest first. */
export const unlockQueue = writable<Achievement[]>([]);
/** The last check failed (shown by the sheet instead of a spinner). */
export const achievementsError = writable<string | null>(null);
/** A check is in flight. */
export const achievementsLoading = writable(false);

const CHECK_DELAY_MS = 350;
/** Most unlocks animated from one check; the rest are summed up in a toast. */
const MAX_PARADE = 3;
const RANK: Record<AchievementTier, number> = { bronze: 0, silver: 1, gold: 2, legendary: 3 };
let started = false;
let unsubs: (() => void)[] = [];
let checkTimer: ReturnType<typeof setTimeout> | undefined;
let running = false;
let again = false;
/** Celebrated this session, so a failed ack can't loop the same unlock. */
const celebrated = new Set<string>();
/** Summed up by the first-run toast; null until that toast has been shown. */
let backfilled: Set<string> | null = null;
/** Backfilled but not stored as seen yet: rides along with every ack until one
 *  succeeds, so no other ack can end the first run without them. */
const backfillPending = new Set<string>();
/** How many the first-run toast sums up, while it waits for the shift to end. */
let backfillToast = 0;

/** A shift is running, or one left unfinished waits to be recovered. */
export const onShift = (t: Pick<TimerState, 'running' | 'recovery_pending'>) => t.running || t.recovery_pending;

/** Medal image per icon id (assets/medals/<id>.webp). */
const MEDALS = import.meta.glob<string>('../../assets/medals/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
});
export function medalUrl(a: Pick<Achievement, 'icon' | 'tier' | 'hidden' | 'met_on'>): string {
  const name = a.hidden && !a.met_on ? `hidden_${a.tier}` : a.icon;
  return MEDALS[`../../assets/medals/${name}.webp`] ?? MEDALS[`../../assets/medals/hidden_${a.tier}.webp`] ?? '';
}

export const unlockedCount = (d: AchievementsData | null) => d?.items.filter((i) => i.met_on).length ?? 0;

export function openAchievements(): Promise<void> {
  return import('../../views/achievements/AchievementsSheet.svelte').then((m) =>
    openSheet<Record<string, never>, void>(m.default, {}),
  );
}

/** Ask Python now (coalesced). Failures are quiet: achievements never block work. */
export async function checkAchievements(): Promise<void> {
  if (running) {
    again = true;
    return;
  }
  running = true;
  achievementsLoading.set(true);
  try {
    do {
      again = false;
      await checkOnce();
    } while (again);
  } finally {
    running = false;
    achievementsLoading.set(false);
  }
}

/** Store ids as seen, plus any backfill still pending. Quiet on failure. */
async function ack(ids: string[]): Promise<void> {
  const all = [...new Set([...ids, ...backfillPending])];
  try {
    const r = await api.ack_achievements(all);
    if (r?.ok) for (const id of all) backfillPending.delete(id);
  } catch {
    // retried with the next ack
  }
}

async function checkOnce(): Promise<void> {
  let r;
  try {
    r = await api.get_achievements();
  } catch {
    r = null;
  }
  if (!r?.ok) {
    achievementsError.set("Couldn't load achievements.");
    return;
  }
  achievementsError.set(null);
  const data: AchievementsData = { items: r.items, newly: r.newly, first_run: r.first_run };
  achievements.set(data);
  // No longer met (the entry was undone or deleted): drop any card still waiting,
  // and celebrate it again if it is earned again.
  const unmet = new Set(data.items.filter((i) => !i.met_on).map((i) => i.id));
  for (const id of unmet) celebrated.delete(id);
  unlockQueue.update((q) => (q.some((a) => unmet.has(a.id)) ? q.filter((a) => !unmet.has(a.id)) : q));
  let newly = data.newly;
  if (data.first_run) {
    if (!backfilled) {
      // Backfill: one summary toast instead of a parade, for what was met when
      // it was first seen, so what a running shift earns later still gets its
      // own card.
      backfilled = new Set(newly);
      for (const id of newly) {
        celebrated.add(id);
        backfillPending.add(id);
      }
      backfillToast = newly.length;
    }
    // Mid-shift nothing is acked, not even the backfill: closing the app before
    // the shift ends keeps the first run, so the toast comes again next launch.
    if (onShift(get(timer))) return;
    // The ack (an empty one still ends the first run) is retried while it fails;
    // anything earned since the backfill is celebrated as a normal unlock.
    const old = backfilled;
    await ack([]);
    showBackfillToast();
    newly = newly.filter((id) => !old.has(id));
  }
  // Mid-shift: the sheet and the tile are up to date, the celebrating waits.
  if (onShift(get(timer))) return;
  showBackfillToast();
  const fresh = data.items.filter((i) => newly.includes(i.id) && !celebrated.has(i.id));
  if (!fresh.length) return;
  for (const a of fresh) celebrated.add(a.id);
  // A big batch (an imported history) gets the rarest few animated and one toast for the rest.
  const parade = fresh.length > MAX_PARADE ? [...fresh].sort((a, b) => RANK[b.tier] - RANK[a.tier]).slice(0, MAX_PARADE) : fresh;
  unlockQueue.update((q) => [...q, ...parade]);
  const summed = fresh.filter((a) => !parade.includes(a));
  const rest = summed.length;
  if (rest) {
    toast(`🏆 …and ${rest} more achievement${rest === 1 ? '' : 's'} unlocked`, {
      tone: 'success',
      label: 'View',
      action: () => void openAchievements(),
      undo: false,
      ms: 10000,
    });
  }
  // The parade is acknowledged by markShown; the summed-up rest is celebrated by the toast.
  if (rest) await ack(summed.map((a) => a.id));
}

function showBackfillToast() {
  const n = backfillToast;
  if (!n || onShift(get(timer))) return;
  backfillToast = 0;
  toast(`🏆 You've already earned ${n} achievement${n === 1 ? '' : 's'}`, {
    tone: 'success',
    label: 'View',
    action: () => void openAchievements(),
    undo: false,
    ms: 10000,
  });
}

/** AchievementUnlock is showing this one: it counts as celebrated now. */
export function markShown(a: Achievement): void {
  void ack([a.id]);
}

function schedule() {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(() => void checkAchievements(), CHECK_DELAY_MS);
}

/** Called once by App after the intro, so nothing pops up under it. */
export function startAchievements(): void {
  if (started) return;
  started = true;
  let lastPrefs = '';
  // The shift ended (saved, discarded, recovered or stopped elsewhere):
  // celebrate what it earned.
  let was = onShift(get(timer));
  unsubs = [
    month.subscribe(() => schedule()),
    timer.subscribe((t) => {
      const now = onShift(t);
      if (was && !now) schedule();
      was = now;
    }),
    settings.subscribe((s) => {
      const key = `${s.pay_rate}|${s.ui_prefs.target_hours}`;
      if (key === lastPrefs) return;
      const first = lastPrefs === '';
      lastPrefs = key;
      if (!first) schedule();
    }),
  ];
}

/** Done showing the head of the queue. */
export function nextUnlock(): void {
  unlockQueue.update((q) => q.slice(1));
}

export function clearUnlocks(): void {
  unlockQueue.set([]);
}

/** Tests only: forget what this session celebrated, and stop listening. */
export function resetAchievementsSession(): void {
  for (const u of unsubs) u();
  unsubs = [];
  started = false;
  clearTimeout(checkTimer);
  celebrated.clear();
  backfilled = null;
  backfillPending.clear();
  backfillToast = 0;
  clearUnlocks();
  achievements.set(null);
  achievementsError.set(null);
}
