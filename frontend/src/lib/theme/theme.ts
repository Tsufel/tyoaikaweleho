import { derived, get, readable, writable, type Readable } from 'svelte/store';
import { api } from '../api/bridge';
import type { Appearance } from '../api/types';
import { settings } from '../stores/settings';

/** Unsaved Settings ▸ Appearance preview; null = use saved setting. */
export const appearancePreview = writable<Appearance | null>(null);

export const systemDark: Readable<boolean> = readable(true, (set) => {
  if (typeof matchMedia !== 'function') return;
  const mq = matchMedia('(prefers-color-scheme: dark)');
  set(mq.matches);
  const on = () => set(mq.matches);
  mq.addEventListener('change', on);
  return () => mq.removeEventListener('change', on);
});

export const appearance: Readable<Appearance> = derived(
  [settings, appearancePreview],
  ([$s, $p]) => $p ?? $s.appearance,
);

/** Effective dark mode. */
export const isDark: Readable<boolean> = derived(
  [appearance, systemDark],
  ([$a, $sys]) => ($a === 'System' ? $sys : $a === 'Dark'),
);

/** Applies data-theme to <html> and keeps the native title bar in sync
 *  (api.set_theme) once `syncNative` is true. */
export function startTheme(syncNative: Readable<boolean>): () => void {
  let last = '';
  const unsub = derived([appearance, isDark, syncNative], (x) => x).subscribe(([$a, $dark, $sync]) => {
    document.documentElement.dataset.theme = $dark ? 'dark' : 'light';
    const key = `${$a}|${$dark}`;
    if ($sync && key !== last) {
      last = key;
      void api.set_theme($a, $dark);
    }
  });
  return unsub;
}

export const currentlyDark = () => get(isDark);
