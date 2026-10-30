import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { PetPose } from '../src/views/pet/petLogic';
import { PET_PARTICLES } from '../src/views/pet/petParticles';
import PetSprite from '../src/views/pet/PetSprite.svelte';
import { SEAM, STILL, spriteLayers } from '../src/views/pet/petSpriteLayers';
import { SPRITE_SIZE } from '../src/views/pet/petState';

const KINDS = ['familiar', 'wizard'] as const;
const POSES: PetPose[] = ['idle', 'fly', 'drowsy', 'sleep'];

afterEach(cleanup);

describe('spriteLayers', () => {
  it('splits standing poses at a seam and keeps flying ones whole', () => {
    for (const kind of KINDS)
      for (const pose of POSES) {
        const { layers } = spriteLayers(kind, pose, SPRITE_SIZE[kind]);
        const parts = pose === 'fly' ? ['whole'] : pose === 'idle' ? ['lower', 'upper', 'still'] : ['lower', 'upper'];
        expect(layers.map((l) => l.part)).toEqual(parts);
        for (const l of layers) expect(l.clip).toMatch(/^polygon\(evenodd, [\d.]+% [\d.]+%(, [\d.]+% [\d.]+%)+\)$/);
      }
  });

  it('gives every particle its own clip and a phase in [0, 1)', () => {
    for (const kind of KINDS)
      for (const pose of POSES) {
        const { bits } = spriteLayers(kind, pose, SPRITE_SIZE[kind]);
        expect(bits).toHaveLength(PET_PARTICLES[`${kind}_${pose}`].length);
        for (const b of bits) {
          expect(b.clip).toMatch(/^inset\([\d.]+% [\d.]+% [\d.]+% [\d.]+%\)$/);
          expect(b.phase).toBeGreaterThanOrEqual(0);
          expect(b.phase).toBeLessThan(1);
        }
      }
  });

  it("floats the z's up in turn, lowest first", () => {
    const { bits } = spriteLayers('wizard', 'drowsy', SPRITE_SIZE.wizard);
    const zs = PET_PARTICLES.wizard_drowsy.map((p, i) => ({ ...p, phase: bits[i].phase })).filter((p) => p.kind === 'z');
    const byBottom = [...zs].sort((a, b) => b.y + b.h - (a.y + a.h));
    expect(byBottom.map((z) => z.phase)).toEqual([0, 1 / 3, 2 / 3].map((p) => +p.toFixed(3)));
  });

  it('keeps the staffs, a star and a hand still: boxes above the seam, on the art grid, clear of everything else', () => {
    const overlap = (a: (typeof STILL)[string][number], b: typeof a) =>
      a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
    expect(Object.keys(STILL).sort()).toEqual(['familiar_idle', 'wizard_idle']);
    for (const [name, boxes] of Object.entries(STILL)) {
      const { w } = SPRITE_SIZE[name.split('_')[0] as 'familiar' | 'wizard'];
      for (const [i, b] of boxes.entries()) {
        for (const v of [b.x, b.y, b.x + b.w, b.y + b.h]) expect(v % 2, `${name} box ${i}`).toBe(1);
        expect(b.x + b.w).toBeLessThanOrEqual(w);
        expect(b.y + b.h).toBeLessThanOrEqual(SEAM[name]);
        for (const o of boxes.slice(i + 1)) expect(overlap(b, o), `${name} box ${i}`).toBe(false);
        for (const p of PET_PARTICLES[name]) expect(overlap(b, p), `${name} box ${i}`).toBe(false);
      }
    }
  });

  it('cuts the still boxes out of the moving layer and draws them on top', () => {
    const points = (clip: string) => clip.match(/%,|%\)/g)!.length;
    for (const kind of KINDS) {
      const name = `${kind}_idle`;
      const { layers } = spriteLayers(kind, 'idle', SPRITE_SIZE[kind]);
      const [lower, upper, still] = layers;
      expect(points(upper.clip)).toBe(5 + 6 * (PET_PARTICLES[name].length + STILL[name].length));
      expect(points(still.clip)).toBe(5 + 6 * STILL[name].length);
      // Under them the lower layer holds islands: each box and one art pixel
      // around it, minus the particles, not reaching into its own band (where
      // an overlap would cancel out under even-odd and leave a hole). Every
      // pixel of that area sits in exactly one island.
      const { w, h } = SPRITE_SIZE[kind];
      const top = SEAM[name] - 2;
      const xy = [...lower.clip.matchAll(/([\d.]+)% ([\d.]+)%/g)].map((m) => [
        Math.round((+m[1] / 100) * w),
        Math.round((+m[2] / 100) * h),
      ]);
      const loops = [];
      for (let i = 5; i < xy.length; i += 6) loops.push({ x0: xy[i][0], y0: xy[i][1], x1: xy[i + 2][0], y1: xy[i + 2][1] });
      const islands = loops.filter((l) => l.y1 <= top);
      expect(islands.length).toBeGreaterThan(0);
      for (const l of loops) expect(l.y0 >= top || l.y1 <= top).toBe(true);
      const within = (b: { x: number; y: number; w: number; h: number }, x: number, y: number) =>
        x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h;
      for (let y = 0; y < top; y++)
        for (let x = 0; x < w; x++) {
          const near = STILL[name].some((b) => within({ x: b.x - 2, y: b.y - 2, w: b.w + 4, h: b.h + 4 }, x, y));
          const want = near && !PET_PARTICLES[name].some((p) => within(p, x, y)) ? 1 : 0;
          const got = islands.filter((l) => x >= l.x0 && x < l.x1 && y >= l.y0 && y < l.y1).length;
          expect(got, `${name} at ${x},${y}`).toBe(want);
        }
    }
  });

  it('cuts the particles out of the body layers they overlap', () => {
    const { layers } = spriteLayers('familiar', 'sleep', SPRITE_SIZE.familiar);
    // the band's corners (5 points) plus 6 per hole: the lower band (from one
    // art pixel above the seam) holds only the sparkle that straddles it
    const points = (clip: string) => clip.match(/%,|%\)/g)!.length;
    expect(points(layers[0].clip)).toBe(5 + 6);
    expect(points(layers[1].clip)).toBe(5 + 6 * PET_PARTICLES.familiar_sleep.length);
  });
});

describe('PetSprite', () => {
  it('stacks clipped copies while animating', () => {
    const { container } = render(PetSprite, { kind: 'familiar', pose: 'drowsy', animate: true });
    const imgs = container.querySelectorAll('img');
    expect(imgs.length).toBe(2 + PET_PARTICLES.familiar_drowsy.length);
    expect(container.querySelectorAll('img.z')).toHaveLength(2);
    expect(container.querySelector('.sprite')!.classList.contains('loop')).toBe(true);
    for (const img of imgs) expect(img.style.clipPath).not.toBe('');
  });

  it('adds the still copy for the idle staff', () => {
    const { container } = render(PetSprite, { kind: 'wizard', pose: 'idle', animate: true });
    expect(container.querySelectorAll('img')).toHaveLength(3 + PET_PARTICLES.wizard_idle.length);
    expect(container.querySelectorAll('img.still')).toHaveLength(1);
  });

  it('is one plain picture when not animating', () => {
    const { container } = render(PetSprite, { kind: 'wizard', pose: 'sleep', animate: false });
    const imgs = container.querySelectorAll('img');
    expect(imgs).toHaveLength(1);
    expect(imgs[0].style.clipPath).toBe('');
    expect(container.querySelector('.sprite')!.classList.contains('loop')).toBe(false);
  });
});
