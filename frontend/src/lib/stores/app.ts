import { derived, get, readable, writable, type Readable } from 'svelte/store';
import { onEvent } from '../api/events';
import type { Bootstrap, Route } from '../api/types';
import { toIsoDate } from '../time';
import { commitEdits } from './editGuard';

export { settings, shifts, dlc, saveUiPrefs } from './settings';
export { motion, lulz, prefersReducedMotion, type MotionLevel } from './motion';
export { modalOpen, focusTopModal } from './modals';

export const bootstrap = writable<Bootstrap | null>(null);
export const errorLogPath = derived(bootstrap, (b) => b?.error_log ?? 'error.log');

/** 'main' shows Timer + Shifts; 'stats'; 'settings' (timer hidden — F5 is off). */
export const route = writable<Route>('main');

/** Top-bar section highlight; 'timer'/'shifts' both live on the main route. */
export type Section = 'timer' | 'shifts' | 'stats';
export const section = writable<Section>('timer');

const now = new Date();
/** Month shown in the entries view. Change it through stores/entries.setViewMonth. */
export const viewMonth = writable<{ year: number; month: number }>({
  year: now.getFullYear(),
  month: now.getMonth() + 1,
});

/** Leave the current route; commits open inline edits first (v1.3 rule). */
export async function navigate(to: Route): Promise<boolean> {
  const from = get(route);
  if (from === to) return true;
  if (from === 'main' && !(await commitEdits())) return false;
  route.set(to);
  if (to === 'stats') section.set('stats');
  else if (to === 'main' && get(section) === 'stats') section.set('timer');
  return true;
}

let pyVisible = true;
/** Page visible and window not minimised: pause rAF/animations/ticks otherwise. */
export const pageVisible: Readable<boolean> = readable(true, (set) => {
  if (typeof document === 'undefined') return;
  const update = () => set(document.visibilityState === 'visible' && pyVisible);
  document.addEventListener('visibilitychange', update);
  const off = onEvent('window:visibility', (p) => {
    pyVisible = p.visible;
    update();
  });
  update();
  return () => {
    document.removeEventListener('visibilitychange', update);
    off();
  };
});

/** Window focused (DOM focus/blur, plus Python's foreground check on
 *  window:visibility). Starts true so a never-focused page still animates. */
export const windowFocused: Readable<boolean> = readable(true, (set) => {
  if (typeof window === 'undefined') return;
  const on = () => set(true);
  const off = () => set(false);
  window.addEventListener('focus', on);
  window.addEventListener('blur', off);
  const offVis = onEvent('window:visibility', (p) => set(p.focused || document.hasFocus()));
  return () => {
    window.removeEventListener('focus', on);
    window.removeEventListener('blur', off);
    offVis();
  };
});

/** Decorative animation (mesh, fire): visible and focused. Timer ticks use
 *  pageVisible only. */
export const animationsActive: Readable<boolean> = derived(
  [pageVisible, windowFocused],
  ([$v, $f]) => $v && $f,
);

/** Today's ISO date; rolls over at midnight. */
export const todayIso: Readable<string> = readable(toIsoDate(new Date()), (set) => {
  const id = setInterval(() => set(toIsoDate(new Date())), 30_000);
  return () => clearInterval(id);
});
