import { derived, get, writable, type Readable } from 'svelte/store';
import type { PetKind, PetStats } from '../../lib/api/types';
import { toIsoDate } from '../../lib/time';
import { openSheet } from '../../lib/stores/confirm';
import { saveUiPrefs, settings } from '../../lib/stores/settings';
import { petStats } from '../../lib/stores/pet';
import { elapsedSeconds, timer } from '../../lib/stores/timer';
import { ringProgress } from '../timer/timerLogic';
import { wallClock } from '../timer/timerActions';
import { energy, level, petName, petPose, type Energy, type Level, type PetPose } from './petLogic';
import { activeSkin, SKIN_ART, unlockedBetween, type PetSkin, type SkinInfo } from './petSkins';

export interface PetView {
  kind: Exclude<PetKind, 'off'>;
  name: string;
  pose: PetPose;
  /** null until the first get_pet_stats answer. */
  energy: Energy | null;
  level: Level | null;
  /** The look drawn: the chosen one once unlocked, else classic. */
  skin: PetSkin;
  /** Holding the after-shift bazooka (rollBazooka): only while awake. */
  bazooka: boolean;
}

/** How often a saved shift brings out the bazooka, and for how long. */
export const BAZOOKA_CHANCE = 0.25;
export const BAZOOKA_MS = 60_000;
const bazookaOut = writable(false);
let bazookaTimer: ReturnType<typeof setTimeout> | undefined;

/** After a saved shift: now and then the pet brings out its bazooka for a
 *  minute, an easter egg rather than a look you pick. True when it did. */
export function rollBazooka(roll = Math.random()): boolean {
  if (!(roll < BAZOOKA_CHANCE)) return false;
  clearTimeout(bazookaTimer);
  bazookaOut.set(true);
  bazookaTimer = setTimeout(putAwayBazooka, BAZOOKA_MS);
  return true;
}

/** Ends the bazooka early (the pet fell asleep or started a shift). */
export function putAwayBazooka(): void {
  clearTimeout(bazookaTimer);
  bazookaTimer = undefined;
  bazookaOut.set(false);
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

// The pet's level at the end of the last run, so the look is right from the
// first frame of the next start, before the stats arrive: a chosen look drawn
// only to swap to classic (its level no longer reached) would flash.
const LEVEL_KEY = 'weleho.petLevel';
let lastLevel: number | null = (() => {
  try {
    const n = Number(localStorage.getItem(LEVEL_KEY));
    return Number.isInteger(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
})();
function rememberLevel(lvl: number | null): number | null {
  if (lvl === null) return lastLevel;
  if (lvl !== lastLevel) {
    lastLevel = lvl;
    try {
      localStorage.setItem(LEVEL_KEY, String(lvl));
    } catch {
      /* not kept: the next start just waits for the stats */
    }
  }
  return lvl;
}

// The last running shift's minutes, kept after it stops until petStats is
// re-read (refreshPetStats runs on stop), so energy and level don't dip.
let carry: { stats: PetStats; minutes: number } | null = null;

/** Everything the companion and the pet sheet show, live: the running shift
 *  charges energy and XP as it ticks, and the pose follows the clock. */
export const petView: Readable<PetView> = derived(
  [settings, petStats, timer, elapsedSeconds, wallClock, bazookaOut],
  ([$s, $stats, $timer, $elapsed, $now, $bazooka]): PetView => {
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
    const lvl = stats ? level(stats.lifetime_minutes) : null;
    const pose = petPose({ running, progress: running ? ringProgress($elapsed, target) : 0, now, stats });
    return {
      kind,
      name: petName(kind, $s.ui_prefs.pet_name),
      pose,
      energy: stats ? energy(stats, now, target) : null,
      level: lvl,
      skin: activeSkin($s.ui_prefs.pet_skin, rememberLevel(lvl?.level ?? null)),
      bazooka: $bazooka && pose === 'idle',
    };
  },
);

/** The Friday fly-by in progress (PetFlyby): the Timer companion steps out
 *  while its pet is crossing the screen, and achievement cards wait for it. */
export const petFlyby = writable<{ id: number; line: string } | null>(null);

const SPRITES = import.meta.glob<string>('../../assets/pets/*.webp', { eager: true, query: '?url', import: 'default' });

/** A sprite by name (petSkins.spriteName), e.g. "wizard_idle_gilded". */
export function spriteUrl(name: string): string {
  return SPRITES[`../../assets/pets/${name}.webp`] ?? '';
}

/** Native sprite size; drawn at 1× (or less) so the pixel art stays crisp.
 *  Every pose of a kind shares this box, so the pet doesn't jump between
 *  poses; the few skin sprites that overhang it are in SKIN_ART. */
export const SPRITE_SIZE: Record<PetView['kind'], { w: number; h: number }> = {
  familiar: { w: 142, h: 122 },
  wizard: { w: 162, h: 140 },
};

/** Where a sprite sits in its kind's box: left edge and width (the height is
 *  the box's). */
export function spriteFrame(kind: PetView['kind'], name: string): { dx: number; w: number; h: number } {
  const box = SPRITE_SIZE[kind];
  const over = SKIN_ART[name];
  return { dx: over?.dx ?? 0, w: over?.w ?? box.w, h: box.h };
}

// The highest pet level seen this session: a looks unlock is news only when
// the level climbs past it while the app runs (a shift, a save), never on the
// first numbers after a start, and each once.
let levelSeen: number | null = null;

/** Looks unlocked since the last call, cheapest first; [] while the level
 *  is unknown, on the first known level, and when nothing new opened up. */
export function newlyUnlockedSkins(lvl: number | null): SkinInfo[] {
  if (lvl === null) return [];
  if (levelSeen === null || lvl <= levelSeen) {
    levelSeen = Math.max(levelSeen ?? lvl, lvl);
    return [];
  }
  const fresh = unlockedBetween(levelSeen, lvl);
  levelSeen = lvl;
  return fresh;
}

/** For tests: forget the levels seen and remembered. */
export function resetSkinUnlocks(): void {
  levelSeen = null;
  lastLevel = null;
  try {
    localStorage.removeItem(LEVEL_KEY);
  } catch {
    /* nothing kept */
  }
}

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
