import type { AchievementTier } from '../../lib/api/types';

export const TIERS: AchievementTier[] = ['bronze', 'silver', 'gold', 'legendary'];

export const TIER_LABEL: Record<AchievementTier, string> = {
  bronze: 'Bronze',
  silver: 'Silver',
  gold: 'Gold',
  legendary: 'Legendary',
};

/** Fire tier for the Lulz milestone flare (fxBus Tier). */
export const TIER_FX: Record<AchievementTier, 1 | 2 | 3 | 4> = { bronze: 1, silver: 2, gold: 3, legendary: 4 };

const UNIT_WORD: Record<string, [string, string]> = {
  shifts: ['shift', 'shifts'],
  days: ['day', 'days'],
  weeks: ['week', 'weeks'],
};

/** "3 / 10 days", "42.5 / 100 h", "€640 / €1 000". */
export function progressText(cur: number, goal: number, unit: string): string {
  const n = (x: number) => {
    const [int, dec] = (Math.floor(x * 10 + 1e-9) / 10).toFixed(1).split('.');
    return int.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + (dec === '0' ? '' : `.${dec}`);
  };
  if (unit === '€') return `€${n(cur)} / €${n(goal)}`;
  const words = UNIT_WORD[unit];
  const u = words ? words[goal === 1 ? 0 : 1] : unit;
  return `${n(cur)} / ${n(goal)} ${u}`;
}

/** "2026-10-30" → "30.10.2026". */
export function shortDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return y && m && d ? `${d}.${m}.${y}` : iso;
}
