// Pet looks, unlocked by pet level (docs/V2_GAMIFICATION_PLAN.md, Cosmetics).
// Only the chosen look is stored (ui_prefs.pet_skin); whether it's unlocked
// follows from the logged hours like everything else about the pet, so a look
// whose level is no longer reached (entries deleted) shows as classic until
// it is again. Each look redraws some of the poses; the rest stay classic.
// The bazooka isn't a look: a saved shift now and then brings it out for a
// while (petState.rollBazooka), in the colours of the look being worn.

import type { PetKind, PetSkinId } from '../../lib/api/types';
import type { PetPose } from './petLogic';

export type PetSkin = PetSkinId;
type Kind = Exclude<PetKind, 'off'>;

export interface SkinInfo {
  id: PetSkin;
  label: string;
  /** Pet level that unlocks it. */
  level: number;
  /** One line per kind, for the picker. */
  blurb: Record<Kind, string>;
  /** Sprite name (assets/pets/<name>.webp) per pose it redraws. */
  art: Record<Kind, Partial<Record<PetPose, string>>>;
}

/** Cheapest first; storage.PET_SKINS lists the same ids. */
export const PET_SKINS: readonly SkinInfo[] = [
  {
    id: 'classic',
    label: 'Classic',
    level: 1,
    blurb: { familiar: 'Hat, staff and wings.', wizard: 'Robe, staff and broom.' },
    art: { familiar: {}, wizard: {} },
  },
  {
    id: 'cosmic',
    label: 'Cosmic',
    level: 5,
    blurb: { familiar: 'Sunset wings for the flight to work.', wizard: 'A sunset robe for late shifts.' },
    art: { familiar: { fly: 'familiar_fly_cosmic' }, wizard: { drowsy: 'wizard_drowsy_cosmic' } },
  },
  {
    id: 'neon',
    label: 'Neon',
    level: 10,
    blurb: { familiar: 'A bazooka in highlighter colours.', wizard: 'A bazooka in highlighter colours.' },
    art: { familiar: { idle: 'familiar_idle_neon' }, wizard: { idle: 'wizard_idle_neon' } },
  },
  {
    id: 'gilded',
    label: 'Gilded',
    level: 20,
    blurb: { familiar: 'Naps in solid gold.', wizard: 'Solid gold, fit for an Archmage.' },
    art: {
      familiar: { sleep: 'familiar_sleep_gilded' },
      wizard: { idle: 'wizard_idle_gilded', drowsy: 'wizard_drowsy_gilded', sleep: 'wizard_sleep_gilded' },
    },
  },
  {
    id: 'legend',
    label: 'Legend',
    level: 25,
    blurb: { familiar: 'Sleeps as a golden dragon.', wizard: 'Gold from hat to bazooka.' },
    art: {
      familiar: { sleep: 'familiar_sleep_legend' },
      wizard: { idle: 'wizard_idle_legend', drowsy: 'wizard_drowsy_gilded', sleep: 'wizard_sleep_gilded' },
    },
  },
];

export const PET_SKIN_IDS = PET_SKINS.map((s) => s.id);

export function skinInfo(id: string | null | undefined): SkinInfo {
  return PET_SKINS.find((s) => s.id === id) ?? PET_SKINS[0];
}

export const isUnlocked = (skin: SkinInfo, level: number) => level >= skin.level;

/** The look to draw: the chosen one once its level is reached, else classic.
 *  While the level isn't known yet (stats loading) the choice stands, so the
 *  pet doesn't flash classic on every start. */
export function activeSkin(chosen: string | null | undefined, level: number | null): PetSkin {
  const skin = skinInfo(chosen);
  return level === null || isUnlocked(skin, level) ? skin.id : 'classic';
}

/** The sprite for a pose in a look: its own art, or the classic pose. */
export function spriteName(kind: Kind, pose: PetPose, skin: PetSkin = 'classic'): string {
  return skinInfo(skin).art[kind][pose] ?? `${kind}_${pose}`;
}

/** The after-shift bazooka in each look's colours; a look without its own
 *  (it doesn't redraw the awake pose) gets the classic one. */
const BAZOOKA: Record<Kind, Partial<Record<PetSkin, string>>> = {
  familiar: { classic: 'familiar_idle_bazooka', neon: 'familiar_idle_neon' },
  wizard: {
    classic: 'wizard_idle_bazooka',
    neon: 'wizard_idle_neon',
    gilded: 'wizard_idle_legend',
    legend: 'wizard_idle_legend',
  },
};
export function bazookaSprite(kind: Kind, skin: PetSkin = 'classic'): string {
  return BAZOOKA[kind][skin] ?? BAZOOKA[kind].classic!;
}

/** The pose the picker previews a look in: the first one it redraws. */
const ORDER: PetPose[] = ['idle', 'fly', 'drowsy', 'sleep'];
export function previewPose(kind: Kind, skin: PetSkin): PetPose {
  return ORDER.find((p) => skinInfo(skin).art[kind][p]) ?? 'idle';
}

/** "idle and asleep": the moments a look redraws, for the picker. */
export const MOMENT: Record<PetPose, string> = {
  idle: 'awake',
  fly: 'on a shift',
  drowsy: 'tired',
  sleep: 'asleep',
};
export function skinMoments(kind: Kind, skin: PetSkin): string {
  const poses = ORDER.filter((p) => skinInfo(skin).art[kind][p]).map((p) => MOMENT[p]);
  return poses.length < 2 ? (poses[0] ?? '') : `${poses.slice(0, -1).join(', ')} and ${poses.at(-1)}`;
}

/** Looks that a level gain from `from` to `to` unlocked, cheapest first. */
export function unlockedBetween(from: number, to: number): SkinInfo[] {
  return PET_SKINS.filter((s) => s.level > from && s.level <= to);
}

/** Sprites drawn past the kind's box (SPRITE_SIZE), in sprite pixels: x of
 *  their left edge in the box and their width. scripts/pet_sprites.py prints
 *  these when it grows a box; the height never changes. */
export const SKIN_ART: Record<string, { dx: number; w: number }> = {
  familiar_idle_bazooka: { dx: -2, w: 154 },
  familiar_idle_neon: { dx: -2, w: 154 },
  wizard_idle_neon: { dx: 0, w: 168 },
};
