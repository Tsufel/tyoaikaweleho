// The Timer card pet, derived from get_pet_stats (docs/V2_GAMIFICATION_PLAN.md).
// Nothing here is stored: energy, level and pose all follow from the logged
// hours, so editing an old entry simply changes the pet. Rest never punishes:
// days the user doesn't usually work don't drain energy, and the pet only naps.

import type { PetKind, PetStats } from '../../lib/api/types';
import { fromIsoDate, toIsoDate } from '../../lib/time';

export type PetPose = 'idle' | 'fly' | 'drowsy' | 'sleep';
export type PetRank = 'Apprentice' | 'Adept' | 'Wizard' | 'Archmage';

export const DEFAULT_PET_NAME: Record<Exclude<PetKind, 'off'>, string> = { familiar: 'Tähti', wizard: 'Weleho' };
export const PET_NAME_MAX = 24;

/** Shown in labels: "Tähti, flying". */
export const POSE_LABEL: Record<PetPose, string> = {
  idle: 'awake',
  fly: 'flying',
  drowsy: 'getting sleepy',
  sleep: 'asleep',
};

const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const weekday = (d: Date) => (d.getDay() + 6) % 7; // Mon 0 … Sun 6
const WEEKDAYS = [0, 1, 2, 3, 4];

export function petName(kind: PetKind, name: string | null | undefined): string {
  const n = (name ?? '').trim();
  return n || (kind === 'wizard' ? DEFAULT_PET_NAME.wizard : DEFAULT_PET_NAME.familiar);
}

/** Weekdays (Mon 0 … Sun 6) worked on at least twice in the 8 weeks of stats;
 *  Mon–Fri until there is enough history to tell. */
export function usualWeekdays(days: PetStats['days']): number[] {
  const count = [0, 0, 0, 0, 0, 0, 0];
  for (const [iso, mins] of Object.entries(days)) {
    const d = fromIsoDate(iso);
    if (d && mins > 0) count[weekday(d)]++;
  }
  const usual = count.flatMap((c, i) => (c >= 2 ? [i] : []));
  return usual.length ? usual : WEEKDAYS;
}

export interface Energy {
  /** 0–100. */
  pct: number;
  /** Hours in the last 7 days, today and the running shift included. */
  hours: number;
  /** target × usual workdays in those 7 days. */
  goal: number;
}

/** Hours in the last 7 days against target × usual workdays. */
export function energy(stats: PetStats, today: Date, targetHours: number, liveMinutes = 0): Energy {
  const target = Math.max(1, Number.isFinite(targetHours) && targetHours > 0 ? targetHours : 8);
  let minutes = Math.max(0, liveMinutes);
  for (let k = 0; k < 7; k++) minutes += stats.days[toIsoDate(addDays(today, -k))] ?? 0;
  const hours = minutes / 60;
  const goal = target * usualWeekdays(stats.days).length;
  return { pct: Math.min(100, Math.round((hours / goal) * 100)), hours, goal };
}

/** Lifetime hours needed to reach level n (level 1 from the start). */
export const levelHours = (n: number) => 10 * Math.max(0, n - 1) ** 1.5;

export interface Level {
  level: number;
  rank: PetRank;
  /** 0–1 towards the next level. */
  progress: number;
  /** Lifetime hours, the running shift included. */
  hours: number;
  /** Lifetime hours at which the next level starts. */
  next: number;
}

export function rankOf(level: number): PetRank {
  return level >= 20 ? 'Archmage' : level >= 10 ? 'Wizard' : level >= 5 ? 'Adept' : 'Apprentice';
}

export function level(lifetimeMinutes: number, liveMinutes = 0): Level {
  const hours = Math.max(0, lifetimeMinutes + Math.max(0, liveMinutes)) / 60;
  // Inverse of levelHours, then nudged for float error at the exact thresholds.
  let n = Math.max(1, Math.floor((hours / 10) ** (2 / 3)) + 1);
  while (n > 1 && levelHours(n) > hours + 1e-9) n--;
  while (levelHours(n + 1) <= hours + 1e-9) n++;
  const lo = levelHours(n);
  const next = levelHours(n + 1);
  return { level: n, rank: rankOf(n), progress: Math.min(1, (hours - lo) / (next - lo)), hours, next };
}

export interface PoseInput {
  running: boolean;
  /** The running shift is past the daily target (the ring is in overtime). */
  overTarget: boolean;
  now: Date;
  stats: PetStats | null;
}

/** fly while working, drowsy in overtime, idle by day, asleep at night or after
 *  a few usual workdays off. Energy never picks the pose. */
export function petPose({ running, overTarget, now, stats }: PoseInput): PetPose {
  if (running) return overTarget ? 'drowsy' : 'fly';
  const h = now.getHours();
  if (h >= 22 || h < 6) return 'sleep';
  if (stats && stats.lifetime_minutes > 0 && restedDays(stats, now)) return 'sleep';
  return 'idle';
}

/** No shift today nor on any of the last 3 usual workdays before it. */
function restedDays(stats: PetStats, now: Date): boolean {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if ((stats.days[toIsoDate(today)] ?? 0) > 0) return false;
  const usual = new Set(usualWeekdays(stats.days));
  let seen = 0;
  for (let k = 1; k <= 28 && seen < 3; k++) {
    const d = addDays(today, -k);
    if (!usual.has(weekday(d))) continue;
    if ((stats.days[toIsoDate(d)] ?? 0) > 0) return false;
    seen++;
  }
  return true;
}
