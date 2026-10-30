import { derived, readable, type Readable } from 'svelte/store';
import { settings } from './settings';

export type MotionLevel = 'full' | 'reduced';

export const prefersReducedMotion: Readable<boolean> = readable(false, (set) => {
  if (typeof matchMedia !== 'function') return;
  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  set(mq.matches);
  const on = () => set(mq.matches);
  mq.addEventListener('change', on);
  return () => mq.removeEventListener('change', on);
});

/** 'reduced' when the OS asks for it or Settings ▸ Reduce effects is on:
 *  no mesh movement, instant springs, no fire. */
export const motion: Readable<MotionLevel> = derived(
  [settings, prefersReducedMotion],
  ([$s, $prefers]) => ($prefers || $s.ui_prefs.reduce_effects ? 'reduced' : 'full'),
);

/** Lulz fire, forced off under reduced motion. */
export const lulz: Readable<boolean> = derived(
  [settings, motion],
  ([$s, $m]) => $s.ui_prefs.lulz && $m === 'full',
);

/** Lulz sound: needs effective Lulz (so also off under reduced motion) and the lulz_sound pref. */
export const lulzSound: Readable<boolean> = derived([settings, lulz], ([$s, $l]) => $l && $s.ui_prefs.lulz_sound);
