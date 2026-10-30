import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { contrastRatio, over } from '../src/lib/theme/tokens';
import { cssBlock } from './cssBlocks';

// WCAG AA on the two base surfaces of each theme (successor of tests/test_theme.py).
const css = readFileSync('src/lib/theme/tokens.css', 'utf8');

const dark = cssBlock(css, /:root\s*[,{]/);
const lightRaw = cssBlock(css, /\[data-theme=['"]?light['"]?\]/);
const light = { ...dark, ...lightRaw };

type Pair = [fg: string, bg: string, min: number];
const TEXT: Pair[] = [
  ['text', 'bg', 4.5],
  ['text', 'glass-solid', 4.5],
  ['text-muted', 'bg', 4.5],
  ['text-muted', 'glass-solid', 4.5],
  ['text-subtle', 'bg', 3],
  ['accent-text', 'bg', 4.5],
  ['accent-text', 'glass-solid', 4.5],
  ['danger-text', 'bg', 4.5],
  ['danger-text', 'glass-solid', 4.5],
  ['success-text', 'bg', 4.5],
  ['warning-text', 'bg', 4.5],
  ['info-text', 'bg', 4.5],
  ['on-accent', 'accent-strong', 4.5],
  ['on-accent', 'accent-strong-2', 4.5],
  ['on-danger', 'danger-strong', 4.5],
  ['on-danger', 'danger-strong-2', 4.5],
  ['on-success', 'success-strong', 4.5],
  ['on-success', 'success-strong-2', 4.5],
  ['focus-ring', 'bg', 3],
];

describe.each([
  ['dark', dark],
  ['light', light],
] as const)('%s theme', (_name, vars) => {
  const resolve = (k: string) => {
    const v = vars[k];
    if (!v) throw new Error(`missing --${k}`);
    return v;
  };
  it.each(TEXT)('%s on %s >= %d', (fg, bg, min) => {
    const rgb = (c: number[]) => `rgb(${c.map((x) => Math.round(x)).join(', ')})`;
    const base = rgb(over(resolve(bg), resolve('bg')));
    const ratio = contrastRatio(resolve(fg), base);
    expect(ratio).toBeGreaterThanOrEqual(min);
  });
});
