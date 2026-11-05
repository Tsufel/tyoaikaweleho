import { readFileSync } from 'node:fs';
import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import { PET_PARTICLES } from '../src/views/pet/petParticles';
import {
  PET_SKINS,
  PET_SKIN_IDS,
  SKIN_ART,
  activeSkin,
  bazookaSprite,
  previewPose,
  skinMoments,
  spriteName,
  unlockedBetween,
} from '../src/views/pet/petSkins';
import { SPRITE_SIZE, spriteFrame } from '../src/views/pet/petState';
import { SEAM } from '../src/views/pet/petSpriteLayers';
import PetSprite from '../src/views/pet/PetSprite.svelte';

// vitest runs from frontend/
const PETS = 'src/assets/pets';
const KINDS = ['familiar', 'wizard'] as const;
const POSES = ['idle', 'fly', 'drowsy', 'sleep'] as const;

/** Width and height from a WebP's header (VP8L, or VP8X around it). */
function webpSize(name: string): { w: number; h: number } {
  const b = readFileSync(`${PETS}/${name}.webp`);
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength);
  const u24 = (at: number) => b[at] | (b[at + 1] << 8) | (b[at + 2] << 16);
  const chunk = String.fromCharCode(...b.subarray(12, 16));
  if (chunk === 'VP8X') return { w: u24(24) + 1, h: u24(27) + 1 };
  if (chunk === 'VP8L') {
    const bits = v.getUint32(21, true);
    return { w: (bits & 0x3fff) + 1, h: ((bits >> 14) & 0x3fff) + 1 };
  }
  throw new Error(`${name}: unexpected WebP chunk ${chunk}`);
}

/** Every sprite a look or the bazooka can draw. */
const SKIN_SPRITES = new Set(
  KINDS.flatMap((kind) => [
    ...PET_SKINS.flatMap((s) => Object.values(s.art[kind])),
    ...PET_SKINS.map((s) => bazookaSprite(kind, s.id)),
  ]),
);

afterEach(cleanup);

describe('pet looks', () => {
  it('lists the same ids as storage.PET_SKINS, cheapest first from classic', () => {
    const py = readFileSync('../storage.py', 'utf8').match(/^PET_SKINS = \(([^)]*)\)/m)![1];
    expect(py.split(',').map((s) => s.trim().replace(/"/g, ''))).toEqual(PET_SKIN_IDS);
    expect(PET_SKINS[0]).toMatchObject({ id: 'classic', level: 1 });
    const levels = PET_SKINS.map((s) => s.level);
    expect([...levels].sort((a, b) => a - b)).toEqual(levels);
    expect(new Set(levels).size).toBe(levels.length);
  });

  it('every look redraws at least one pose of each kind, except classic', () => {
    for (const s of PET_SKINS.slice(1)) for (const kind of KINDS) expect(Object.keys(s.art[kind]).length).toBeGreaterThan(0);
  });

  it('draws the chosen look once its level is reached, else classic', () => {
    expect(activeSkin('neon', 10)).toBe('neon');
    expect(activeSkin('neon', 9)).toBe('classic');
    expect(activeSkin('legend', 30)).toBe('legend');
    // the level isn't known yet: the choice stands rather than flashing classic
    expect(activeSkin('gilded', null)).toBe('gilded');
    // unknown ids (an old build's bazooka) are classic
    expect(activeSkin('bazooka', 30)).toBe('classic');
    expect(activeSkin(undefined, 30)).toBe('classic');
  });

  it('names a look’s own art, and the classic pose for the rest', () => {
    expect(spriteName('wizard', 'idle')).toBe('wizard_idle');
    expect(spriteName('wizard', 'idle', 'gilded')).toBe('wizard_idle_gilded');
    expect(spriteName('wizard', 'fly', 'gilded')).toBe('wizard_fly');
    expect(spriteName('familiar', 'fly', 'cosmic')).toBe('familiar_fly_cosmic');
    expect(spriteName('familiar', 'idle', 'cosmic')).toBe('familiar_idle');
  });

  it('brings out the bazooka in the colours of the look worn', () => {
    expect(bazookaSprite('wizard', 'classic')).toBe('wizard_idle_bazooka');
    expect(bazookaSprite('wizard', 'cosmic')).toBe('wizard_idle_bazooka');
    expect(bazookaSprite('wizard', 'neon')).toBe('wizard_idle_neon');
    expect(bazookaSprite('wizard', 'gilded')).toBe('wizard_idle_legend');
    expect(bazookaSprite('wizard', 'legend')).toBe('wizard_idle_legend');
    expect(bazookaSprite('familiar', 'neon')).toBe('familiar_idle_neon');
    expect(bazookaSprite('familiar', 'gilded')).toBe('familiar_idle_bazooka');
  });

  it('previews a look in a pose it redraws, and says when it shows', () => {
    expect(previewPose('wizard', 'classic')).toBe('idle');
    expect(previewPose('familiar', 'cosmic')).toBe('fly');
    expect(previewPose('familiar', 'gilded')).toBe('sleep');
    expect(skinMoments('familiar', 'gilded')).toBe('asleep');
    expect(skinMoments('wizard', 'gilded')).toBe('awake, tired and asleep');
    expect(skinMoments('wizard', 'classic')).toBe('');
  });

  it('lists the looks a level gain unlocked', () => {
    expect(unlockedBetween(4, 5).map((s) => s.id)).toEqual(['cosmic']);
    expect(unlockedBetween(2, 25).map((s) => s.id)).toEqual(['cosmic', 'neon', 'gilded', 'legend']);
    expect(unlockedBetween(5, 9)).toEqual([]);
    expect(unlockedBetween(1, 1)).toEqual([]);
  });
});

describe('look sprites', () => {
  it('exist, fill their frame, and know where to breathe', () => {
    for (const name of SKIN_SPRITES) {
      const kind = name.split('_')[0] as (typeof KINDS)[number];
      const frame = spriteFrame(kind, name);
      expect(webpSize(name), name).toEqual({ w: frame.w, h: frame.h });
      expect(PET_PARTICLES[name], name).toBeDefined();
      // flying hovers whole; every other pose breathes above a seam on an odd row
      if (!name.includes('_fly')) expect(SEAM[name] % 2, name).toBe(1);
    }
    // the classic poses keep the kind's box
    for (const kind of KINDS) for (const pose of POSES) expect(webpSize(`${kind}_${pose}`)).toEqual(SPRITE_SIZE[kind]);
  });

  it('overhang the box by whole art pixels, never above or below it', () => {
    for (const [name, o] of Object.entries(SKIN_ART)) {
      const box = SPRITE_SIZE[name.split('_')[0] as (typeof KINDS)[number]];
      expect(Math.abs(o.dx % 2), name).toBe(0);
      expect(o.dx, name).toBeLessThanOrEqual(0);
      expect(o.dx + o.w, name).toBeGreaterThanOrEqual(box.w);
      expect((o.w - box.w) % 2, name).toBe(0);
    }
  });

  it('every sprite file is drawn by some pose or look', () => {
    const used = new Set([...SKIN_SPRITES, ...KINDS.flatMap((k) => POSES.map((p) => `${k}_${p}`))]);
    for (const name of Object.keys(PET_PARTICLES)) expect(used.has(name), name).toBe(true);
  });
});

describe('PetSprite looks', () => {
  const src = (c: HTMLElement) => c.querySelector('img')!.getAttribute('src') ?? '';

  it('draws the look’s art, overhanging the box where it is wider', () => {
    const { container } = render(PetSprite, { kind: 'wizard', pose: 'idle', skin: 'neon', animate: false });
    expect(src(container)).toContain('wizard_idle_neon');
    const art = container.querySelector<HTMLElement>('.art')!;
    expect(parseFloat(art.style.width)).toBeCloseTo((168 / 162) * 100);
  });

  it('holds the bazooka only while awake', () => {
    const awake = render(PetSprite, { kind: 'familiar', pose: 'idle', bazooka: true, animate: false });
    expect(src(awake.container)).toContain('familiar_idle_bazooka');
    expect(parseFloat(awake.container.querySelector<HTMLElement>('.art')!.style.left)).toBeLessThan(0);
    const asleep = render(PetSprite, { kind: 'familiar', pose: 'sleep', bazooka: true, animate: false });
    expect(src(asleep.container)).toMatch(/familiar_sleep\.webp/);
  });

  it('animates a look’s sprite in layers like the classic ones', () => {
    const { container } = render(PetSprite, { kind: 'wizard', pose: 'idle', skin: 'gilded', animate: true });
    expect(container.querySelectorAll('img.still')).toHaveLength(1);
    expect(container.querySelectorAll('img').length).toBe(3 + PET_PARTICLES.wizard_idle_gilded.length);
  });
});
