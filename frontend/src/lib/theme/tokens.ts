// JS-side tokens (canvas / charts / tests). CSS values live in tokens.css.

export const AURORA = {
  violet: '#7c5cff',
  cyan: '#22d3ee',
  magenta: '#f472b6',
  amber: '#fbbf24',
  teal: '#2dd4bf',
} as const;

/** Categorical chart palette, readable on both themes. */
export const CHART_SERIES = ['#7c5cff', '#22d3ee', '#f472b6', '#fbbf24', '#2dd4bf', '#a3e635', '#fb923c', '#60a5fa'];

/** Fire palette (Lulz), hot → cool. */
export const FIRE = ['#fff7d6', '#ffd166', '#ff9f1c', '#ff5d2a', '#d62828', '#6a040f'] as const;

/** Read a CSS custom property from :root (current theme). */
export function cssVar(name: string): string {
  if (typeof document === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// ── WCAG contrast ────────────────────────────────────────────────

/** '#rgb' | '#rrggbb' | 'rgb(a)(…)' → [r, g, b, a] (0–255, a 0–1). */
export function parseColor(c: string): [number, number, number, number] {
  const s = c.trim();
  let m = /^#([0-9a-f]{3})$/i.exec(s);
  if (m) {
    const [r, g, b] = m[1].split('').map((x) => parseInt(x + x, 16));
    return [r, g, b, 1];
  }
  m = /^#([0-9a-f]{6})$/i.exec(s);
  if (m) {
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  m = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i.exec(s);
  if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
  throw new Error(`Unparseable colour: ${c}`);
}

/** Composite `fg` (possibly translucent) over opaque `bg`. */
export function over(fg: string, bg: string): [number, number, number] {
  const [r, g, b, a] = parseColor(fg);
  const [R, G, B] = parseColor(bg);
  return [r * a + R * (1 - a), g * a + G * (1 - a), b * a + B * (1 - a)];
}

export function luminance([r, g, b]: [number, number, number] | number[]): number {
  const ch = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
}

export function contrastRatio(a: string, b: string): number {
  const base = parseColor(b);
  if (base[3] < 1) throw new Error('background must be opaque');
  const la = luminance(over(a, b));
  const lb = luminance(base);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}
