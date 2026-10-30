import { derived, readable, writable, type Readable } from 'svelte/store';
import { settings } from './settings';
import { motion } from './motion';
import { REFRACT_ENABLED } from '../glass/surfaces';

export function media(q: string): Readable<boolean> {
  return readable(false, (set) => {
    if (typeof matchMedia !== 'function') return;
    const mq = matchMedia(q);
    set(mq.matches);
    const on = () => set(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  });
}

export const prefersReducedTransparency = media('(prefers-reduced-transparency: reduce)');
export const prefersHighContrast = media('(prefers-contrast: more), (forced-colors: active)');

/** Why the OS keeps Liquid glass off, if it does. */
export type GlassBlock = 'transparency' | 'contrast' | null;
export const glassBlock: Readable<GlassBlock> = derived(
  [prefersReducedTransparency, prefersHighContrast],
  ([t, c]): GlassBlock => (t ? 'transparency' : c ? 'contrast' : null),
);

/** Lazy so tests can stub CSS.supports. */
export function canRefract(): boolean {
  return (
    REFRACT_ENABLED &&
    typeof CSS !== 'undefined' &&
    typeof CSS.supports === 'function' &&
    CSS.supports('backdrop-filter', 'url(#a)')
  );
}

/** Set by the registry on map-generation failure or by the frame guard; session-only. */
export const refractBroken = writable(false);

/** 'off': today's look; 'css': tint/sheen/rim only; 'refract': plus SVG lenses. */
export type GlassMode = 'off' | 'css' | 'refract';
export const glassMode: Readable<GlassMode> = derived(
  [settings, glassBlock, refractBroken],
  ([s, b, broken]): GlassMode =>
    !s?.ui_prefs.liquid_glass || b
      ? 'off'
      : s.ui_prefs.reduce_effects || broken || !canRefract()
        ? 'css'
        : 'refract',
);

/** Pointer light, gel, thumb lens, materialize: needs full motion. */
export const glassLive: Readable<boolean> = derived(
  [glassMode, motion],
  ([g, m]) => g !== 'off' && m === 'full',
);

/** html[data-glass='liquid'] (css and refract) and html[data-refract='on']
 *  (refract only). Off deletes both, so the OFF DOM is exactly today's. */
export function applyGlassMode(root: HTMLElement, mode: GlassMode): void {
  const d = root.dataset;
  if (mode === 'off') {
    delete d.glass;
    delete d.refract;
    return;
  }
  d.glass = 'liquid';
  if (mode === 'refract') d.refract = 'on';
  else delete d.refract;
}

/** Keeps <html> in sync with glassMode; started next to startTheme. */
export function startGlass(root: HTMLElement = document.documentElement): () => void {
  const unsub = glassMode.subscribe((m) => applyGlassMode(root, m));
  return () => {
    unsub();
    applyGlassMode(root, 'off');
  };
}
