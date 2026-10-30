import { derived, get, type Readable } from 'svelte/store';
import type { PetKind, PetStats } from '../../lib/api/types';
import { toIsoDate } from '../../lib/time';
import { openSheet } from '../../lib/stores/confirm';
import { saveUiPrefs, settings } from '../../lib/stores/settings';
import { petStats } from '../../lib/stores/pet';
import { elapsedSeconds, timer } from '../../lib/stores/timer';
import { ringProgress } from '../timer/timerLogic';
import { wallClock } from '../timer/timerActions';
import { energy, level, petName, petPose, type Energy, type Level, type PetPose } from './petLogic';

export interface PetView {
  kind: Exclude<PetKind, 'off'>;
  name: string;
  pose: PetPose;
  /** null until the first get_pet_stats answer. */
  energy: Energy | null;
  level: Level | null;
}

/** The running shift's minutes on top of stats, as if already saved. */
function withLive(stats: PetStats, minutes: number, now: Date): PetStats {
  if (minutes <= 0) return stats;
  const today = toIsoDate(now);
  return {
    lifetime_minutes: stats.lifetime_minutes + minutes,
    days: { ...stats.days, [today]: (stats.days[today] ?? 0) + minutes },
  };
}

// The last running shift's minutes, kept after it stops until petStats is
// re-read (refreshPetStats runs on stop), so energy and level don't dip.
let carry: { stats: PetStats; minutes: number } | null = null;

/** Everything the companion and the pet sheet show, live: the running shift
 *  charges energy and XP as it ticks, and the pose follows the clock. */
export const petView: Readable<PetView> = derived(
  [settings, petStats, timer, elapsedSeconds, wallClock],
  ([$s, $stats, $timer, $elapsed, $now]): PetView => {
    const kind: PetView['kind'] = $s.ui_prefs.pet === 'wizard' ? 'wizard' : 'familiar';
    const target = $s.ui_prefs.target_hours || 8;
    const running = $timer.running;
    const now = new Date($now);
    let stats = $stats;
    if (stats && running) {
      carry = { stats, minutes: Math.max(0, $elapsed) / 60 };
      stats = withLive(stats, carry.minutes, now);
    } else if (stats && carry?.stats === stats) {
      stats = withLive(stats, carry.minutes, now);
    } else {
      carry = null;
    }
    return {
      kind,
      name: petName(kind, $s.ui_prefs.pet_name),
      pose: petPose({ running, overTarget: running && ringProgress($elapsed, target) > 1, now, stats }),
      energy: stats ? energy(stats, now, target) : null,
      level: stats ? level(stats.lifetime_minutes) : null,
    };
  },
);

const SPRITES = import.meta.glob<string>('../../assets/pets/*.webp', { eager: true, query: '?url', import: 'default' });

export function spriteUrl(kind: PetView['kind'], pose: PetPose): string {
  return SPRITES[`../../assets/pets/${kind}_${pose}.webp`] ?? '';
}

/** Native sprite size; drawn at 1× (or less) so the pixel art stays crisp. */
export const SPRITE_SIZE: Record<PetView['kind'], { w: number; h: number }> = {
  familiar: { w: 142, h: 122 },
  wizard: { w: 162, h: 140 },
};

type Box = Pick<DOMRect, 'left' | 'top' | 'right' | 'bottom'>;
export interface PetSpot {
  /** From the card's top-left corner. */
  x: number;
  y: number;
  w: number;
}
/** Smaller than this (px wide) and the companion hides. */
export const PET_MIN_W = 64;
/** Gap kept from the card edge and the neighbours. */
const PAD = 16;

/** Where the Timer companion fits: the bigger of the free spots under the
 *  controls (bottom-right corner) and beside the ring (on its baseline), at
 *  most 1×; null when neither fits PET_MIN_W. */
export function petSpot(card: Box, ring: Box, controls: Box, size: { w: number; h: number }): PetSpot | null {
  const ar = size.h / size.w;
  const below = Math.floor(
    Math.min(size.w, card.right - card.left - 2 * PAD, (card.bottom - PAD - controls.bottom - PAD / 2) / ar),
  );
  const left = ring.right + PAD / 2;
  const beside = Math.floor(Math.min(size.w, card.right - PAD - left, (ring.bottom - ring.top) / ar));
  if (Math.max(below, beside) < PET_MIN_W) return null;
  if (below >= beside) {
    return { x: card.right - card.left - PAD - below, y: card.bottom - card.top - PAD - below * ar, w: below };
  }
  return {
    x: left - card.left + (card.right - PAD - left - beside) / 2,
    y: ring.bottom - card.top - beside * ar,
    w: beside,
  };
}

export function openPetSheet(): Promise<void> {
  return import('./PetSheet.svelte').then((m) => openSheet<Record<string, never>, void>(m.default, {}));
}

/** "7.5" under 10 h, whole hours above. */
export const fmtHours = (h: number) => (h < 10 ? (Math.round(h * 10) / 10).toString() : Math.round(h).toString());

/** Save a typed pet name (whitespace tidied, as Python does) unless it's
 *  unchanged; returns what the field should show afterwards. */
export async function commitPetName(draft: string): Promise<string> {
  const name = draft.split(/\s+/).filter(Boolean).join(' ');
  if (name === get(settings).ui_prefs.pet_name) return name;
  await saveUiPrefs({ pet_name: name });
  return get(settings).ui_prefs.pet_name;
}
