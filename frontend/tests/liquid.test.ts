import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { contrastRatio, over, parseColor } from '../src/lib/theme/tokens';
import { cssBlock, splitSelectors, stripComments, topLevelRules } from './cssBlocks';

// Liquid glass tokens: scoping, dark/light parity and a token-level contrast lock.
const tokens = readFileSync('src/lib/theme/tokens.css', 'utf8');
const liquid = readFileSync('src/lib/theme/liquid.css', 'utf8');

const baseDark = cssBlock(tokens, /:root\s*[,{]/);
const baseLight = { ...baseDark, ...cssBlock(tokens, /\[data-theme=['"]?light['"]?\]/) };
const lgDark = cssBlock(liquid, /:root\[data-glass='liquid'\]\s*\{/);
const lgLight = cssBlock(liquid, /\[data-glass='liquid'\]\[data-theme='light'\]\s*\{/);

const SCOPES = ["[data-glass='liquid']", "[data-refract='on']"];

describe('liquid.css structure', () => {
  it('scopes every selector under the liquid or refract attribute', () => {
    const rules = topLevelRules(liquid);
    expect(rules.length).toBeGreaterThan(5);
    for (const { prelude } of rules) {
      if (prelude.startsWith('@property') || prelude.startsWith('@keyframes')) continue;
      expect(prelude.startsWith('@'), `unexpected at-rule ${prelude}`).toBe(false);
      for (const sel of splitSelectors(prelude)) {
        expect(
          SCOPES.some((s) => sel.includes(s)),
          `unscoped selector: ${sel}`,
        ).toBe(true);
      }
    }
  });

  it('redeclares every dark-liquid key in the light-liquid block', () => {
    const missing = Object.keys(lgDark).filter((k) => !(k in lgLight));
    expect(missing).toEqual([]);
  });

  it('leaves solid fills, borders and mesh alone', () => {
    const declared = [...stripComments(liquid).matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]);
    const bad = declared.filter((k) => k === '--glass-solid' || k === '--glass-border' || k.startsWith('--mesh-'));
    expect(bad).toEqual([]);
  });

  it('keeps one declaration per line', () => {
    for (const line of stripComments(liquid).split('\n')) {
      expect((line.match(/;/g) ?? []).length, line).toBeLessThanOrEqual(1);
    }
  });

  it.each([
    ['dark', lgDark],
    ['light', lgLight],
  ] as const)('every %s colour token parses', (_n, block) => {
    for (const [k, v] of Object.entries(block)) {
      if (!/^(#|rgb)/.test(v)) continue;
      const c = parseColor(v);
      expect(c.every((x) => Number.isFinite(x)), `--${k}: ${v}`).toBe(true);
    }
  });
});

const rgb = (c: number[]) => `rgb(${c.map((x) => Math.round(x)).join(', ')})`;
/** a over b (both strings), as an opaque rgb() string. */
const comp = (a: string, b: string) => rgb(over(a, b));

type Vars = Record<string, string>;
const THEMES: [string, Vars, Vars][] = [
  ['dark', baseDark, { ...baseDark, ...lgDark }],
  ['light', baseLight, { ...baseLight, ...lgLight }],
];
const MESH = ['mesh-1', 'mesh-2', 'mesh-3', 'mesh-4', 'mesh-5'];
const FILLS = ['glass-fill', 'glass-fill-strong'];
const STRONG: [string, number][] = [
  ['text', 4.5],
  ['text-muted', 4.5],
  ['accent-text', 4.5],
  ['danger-text', 4.5],
  ['text-subtle', 3],
];

describe.each(THEMES)('%s liquid contrast', (_name, base, lg) => {
  const v = (vars: Vars, k: string) => {
    const x = vars[k];
    if (!x) throw new Error(`missing --${k}`);
    return x;
  };
  const bg = v(base, 'bg');
  const singles: [string, string][] = [
    ['bg', rgb(over(bg, bg))],
    ['bg-2', comp(v(base, 'bg-2'), bg)],
    ...MESH.map((m): [string, string] => [m, comp(v(base, m), bg)]),
  ];
  const pairs: [string, string][] = [];
  for (const a of MESH) for (const b of MESH) if (a !== b) pairs.push([`${a}+${b}`, comp(v(base, b), comp(v(base, a), bg))]);

  // with the top sheen (where the gradient starts) and without (its lower part)
  const liquidSurfaces = (fill: string, probe: string) => {
    const under = comp(v(lg, fill), probe);
    return [under, comp(v(lg, 'lg-sheen'), under)];
  };

  it.each(FILLS)('text on %s stays readable over every single probe', (fill) => {
    for (const [pname, probe] of singles) {
      for (const surface of liquidSurfaces(fill, probe)) {
        for (const [fg, min] of STRONG) {
          const r = contrastRatio(v(lg, fg), surface);
          expect(r, `${fg} on ${fill} over ${pname}`).toBeGreaterThanOrEqual(min);
        }
      }
    }
  });

  // Spec §8.5: the liquid surface (sheen over fill) against today's flat fill.
  // Today's fill can already dip under 4.5 on stacked peaks, hence
  // non-regression rather than a floor.
  it.each(FILLS)('%s never reads worse than today over stacked blobs', (fill) => {
    for (const [pname, probe] of pairs) {
      const today = comp(v(base, fill), probe);
      const liquidTop = comp(v(lg, 'lg-sheen'), comp(v(lg, fill), probe));
      for (const [fg] of STRONG) {
        const was = contrastRatio(v(base, fg), today);
        const now = contrastRatio(v(lg, fg), liquidTop);
        expect(now, `${fg} on ${fill} over ${pname}`).toBeGreaterThanOrEqual(was - 1e-9);
      }
    }
  });

  it('text on the clear chip tint stays readable', () => {
    for (const [pname, probe] of singles) {
      const under = comp(v(lg, 'lg-clear'), probe);
      for (const surface of [under, comp(v(lg, 'lg-sheen'), under)]) {
        expect(contrastRatio(v(lg, 'text'), surface), `text on clear over ${pname}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it.each(['accent-strong', 'accent-strong-2'])('on-accent survives the button gloss on %s', (k) => {
    const surface = comp('rgba(255, 255, 255, 0.05)', v(lg, k));
    expect(contrastRatio(v(lg, 'on-accent'), surface)).toBeGreaterThanOrEqual(4.5);
  });

  it('chart knockouts still match the liquid fill (drift <= 12 per channel)', () => {
    const was = over(v(base, 'glass-fill'), bg);
    const now = over(v(lg, 'glass-fill'), bg);
    for (let i = 0; i < 3; i++) expect(Math.abs(was[i] - now[i])).toBeLessThanOrEqual(12);
  });
});
