import type { PetPose } from './petLogic';
import { PET_PARTICLES, type PetParticle } from './petParticles';

// PetSprite draws one sprite several times, each copy clipped to one part, so
// the parts can move on their own without any extra art: the body in two
// layers split at a seam row (the rows above it breathe or nod, except for
// a few still boxes), and every sparkle and z as a bit of its own.

/** Sprite row where the body splits: rows above it move, rows below stay.
 *  Each art pixel is two sprite rows and the art's pixels start on odd rows,
 *  so the seams sit on odd rows too (an even one would cut a pixel in half
 *  and show a sliver while the top moves). Flying poses have none and hover
 *  whole. */
export const SEAM: Record<string, number> = {
  familiar_idle: 85,
  familiar_drowsy: 71,
  familiar_sleep: 97,
  wizard_idle: 93,
  wizard_drowsy: 67,
  wizard_sleep: 99,
};

type Box = Pick<PetParticle, 'x' | 'y' | 'w' | 'h'>;

/** Parts above the seam that stay with the still rows instead of moving: the
 *  staffs stand on the ground, so they shouldn't shrink with each breath (and
 *  the wizard keeps his grip on his), nor should the stars hanging in the air
 *  or the wizard's raised hand. Sprite pixels, on the art's odd grid,
 *  clear of each other and of the particles. */
export const STILL: Record<string, Box[]> = {
  familiar_idle: [
    // orb, then the shaft stepping down to the right
    { x: 17, y: 55, w: 22, h: 6 },
    { x: 15, y: 61, w: 24, h: 12 },
    { x: 19, y: 73, w: 20, h: 6 },
    { x: 27, y: 79, w: 12, h: 6 },
    // the yellow star by the hat brim, which hangs in the air
    { x: 25, y: 45, w: 6, h: 6 },
  ],
  wizard_idle: [
    // orb, its prongs and the shaft down to his hand
    { x: 129, y: 25, w: 16, h: 6 },
    { x: 127, y: 31, w: 18, h: 8 },
    { x: 129, y: 39, w: 12, h: 4 },
    { x: 129, y: 43, w: 10, h: 4 },
    { x: 129, y: 47, w: 8, h: 8 },
    { x: 127, y: 55, w: 8, h: 8 },
    // the hand on it, then the shaft below
    { x: 121, y: 63, w: 16, h: 16 },
    { x: 119, y: 79, w: 8, h: 14 },
    // the two faint sparkles beside the orb, which hang in the air with it
    { x: 145, y: 23, w: 6, h: 8 },
    { x: 137, y: 47, w: 6, h: 6 },
    // his raised pointing hand, down to the wrist: the fingers, then the
    // palm out to its outline (the cuff above it moves with the sleeve)
    { x: 47, y: 51, w: 20, h: 14 },
    { x: 47, y: 65, w: 22, h: 6 },
  ],
};

export interface SpriteLayer {
  part: 'upper' | 'lower' | 'whole' | 'still';
  clip: string;
}
export interface SpriteBit {
  kind: PetParticle['kind'];
  clip: string;
  /** Where in its loop this bit starts, as a fraction of the loop. */
  phase: number;
}

const pct = (v: number, of: number) => `${+((v / of) * 100).toFixed(3)}%`;

/** a without the parts of it under any of cuts, as boxes that don't overlap. */
function minus(a: Box, cuts: Box[]): Box[] {
  let out = [a];
  for (const c of cuts)
    out = out.flatMap((r) => {
      const x0 = Math.max(r.x, c.x);
      const x1 = Math.min(r.x + r.w, c.x + c.w);
      const y0 = Math.max(r.y, c.y);
      const y1 = Math.min(r.y + r.h, c.y + c.h);
      if (x0 >= x1 || y0 >= y1) return [r];
      return [
        { x: r.x, y: r.y, w: r.w, h: y0 - r.y },
        { x: r.x, y: y1, w: r.w, h: r.y + r.h - y1 },
        { x: r.x, y: y0, w: x0 - r.x, h: y1 - y0 },
        { x: x1, y: y0, w: r.x + r.w - x1, h: y1 - y0 },
      ].filter((p) => p.w > 0 && p.h > 0);
    });
  return out;
}

/** Rows top..bottom with the holes cut out, plus islands outside those rows:
 *  an even-odd polygon of the band and each box, joined to the band's corner
 *  by lines walked there and back (they add no area). The holes must not
 *  overlap each other, nor the islands. */
function band(top: number, bottom: number, holes: Box[], w: number, h: number, islands: Box[] = []): string {
  const pts: [number, number][] = [[0, top], [w, top], [w, bottom], [0, bottom], [0, top]];
  const loop = (x0: number, y0: number, x1: number, y1: number) =>
    pts.push([x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0], [0, top]);
  for (const b of holes) {
    const y0 = Math.max(b.y, top);
    const y1 = Math.min(b.y + b.h, bottom);
    if (y0 < y1) loop(b.x, y0, b.x + b.w, y1);
  }
  for (const b of islands) loop(b.x, b.y, b.x + b.w, b.y + b.h);
  return `polygon(evenodd, ${pts.map(([x, y]) => `${pct(x, w)} ${pct(y, h)}`).join(', ')})`;
}

/** The copies PetSprite stacks for one pose, bottom first. */
export function spriteLayers(
  kind: string,
  pose: PetPose,
  size: { w: number; h: number },
): { layers: SpriteLayer[]; bits: SpriteBit[] } {
  const { w, h } = size;
  const name = `${kind}_${pose}`;
  const bits = PET_PARTICLES[name] ?? [];
  const seam = SEAM[name];
  const still = STILL[name] ?? [];
  // The still boxes are drawn on top, so what moves passes behind the staff
  // and the hand on it. The lower layer reaches one art pixel up under the
  // upper one, and one around each still box, so the clip edges (which blend
  // the pixels they cross) never meet over nothing at rest. The upper layer
  // moves with its holes, so that margin also fills the hole's new spot.
  const under: Box[] = [];
  for (const b of still) {
    const grown = { x: Math.max(b.x - 2, 0), y: Math.max(b.y - 2, 0), w: 0, h: 0 };
    grown.w = Math.min(b.x + b.w + 2, w) - grown.x;
    grown.h = Math.min(b.y + b.h + 2, (seam ?? h) - 2) - grown.y;
    if (grown.h > 0) under.push(...minus(grown, [...under, ...bits]));
  }
  const layers: SpriteLayer[] =
    seam === undefined
      ? [{ part: 'whole', clip: band(0, h, bits, w, h) }]
      : [
          { part: 'lower', clip: band(seam - 2, h, bits, w, h, under) },
          { part: 'upper', clip: band(0, seam, [...bits, ...still], w, h) },
          // an empty band, so just the boxes
          ...(still.length ? [{ part: 'still' as const, clip: band(0, 0, [], w, h, still) }] : []),
        ];

  // Sparkles start spread around their loop. The z's float up in turn,
  // lowest (nearest the sleeper) first.
  const groups = (k: PetParticle['kind']) => [...new Set(bits.filter((b) => b.kind === k).map((b) => b.group))];
  const sparks = groups('spark');
  const bottom = (g: number) => Math.max(...bits.filter((b) => b.group === g).map((b) => b.y + b.h));
  const zs = groups('z').sort((a, b) => bottom(b) - bottom(a));
  const phase = (b: PetParticle) =>
    b.kind === 'z' ? zs.indexOf(b.group) / zs.length : (sparks.indexOf(b.group) * 0.618) % 1;

  return {
    layers,
    bits: bits.map((b) => ({
      kind: b.kind,
      clip: `inset(${pct(b.y, h)} ${pct(w - b.x - b.w, w)} ${pct(h - b.y - b.h, h)} ${pct(b.x, w)})`,
      phase: +phase(b).toFixed(3),
    })),
  };
}
