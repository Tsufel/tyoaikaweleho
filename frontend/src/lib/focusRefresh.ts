import { get } from 'svelte/store';
import { month, refreshMonth } from './stores/entries';
import { isModalOpen } from './stores/modals';

/** At most one refresh per this many ms of focus / visibility changes. */
export const FOCUS_REFRESH_MS = 5000;

/** True while the user types somewhere (an inline time edit, a filter box):
 *  a reload then could redraw the row under the caret. */
export function isTyping(el: Element | null | undefined): boolean {
  if (!el) return false;
  const tag = el.tagName;
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag === 'INPUT') {
    const type = ((el as HTMLInputElement).type || 'text').toLowerCase();
    return !['button', 'checkbox', 'radio', 'range', 'submit', 'reset', 'color', 'file'].includes(type);
  }
  return (el as HTMLElement).isContentEditable === true;
}

export interface FocusRefreshOpts {
  refresh: () => unknown;
  /** True when a refresh now would disturb the user (a modal, typing). */
  busy: () => boolean;
  now?: () => number;
  intervalMs?: number;
}

/** A trigger that runs `refresh` unless busy or run less than `intervalMs`
 *  ago. A skipped (busy) call doesn't count toward the interval. Returns
 *  whether it ran. */
export function createFocusRefresher(opts: FocusRefreshOpts): () => boolean {
  const now = opts.now ?? Date.now;
  const interval = opts.intervalMs ?? FOCUS_REFRESH_MS;
  let last = -Infinity;
  return () => {
    const t = now();
    if (t - last < interval || opts.busy()) return false;
    last = t;
    void opts.refresh();
    return true;
  };
}

/** Re-read the shown month when the window comes back (focus, or the page
 *  turning visible), so edits another process made to data.json show up.
 *  Nothing happens before the first month loaded, while a modal is open or
 *  while the user types. Returns the remover. */
export function startFocusRefresh(win: Window = window, doc: Document = document): () => void {
  const trigger = createFocusRefresher({
    refresh: () => refreshMonth(),
    busy: () => get(month) === null || isModalOpen() || isTyping(doc.activeElement),
  });
  const onFocus = () => void trigger();
  const onVisible = () => {
    if (doc.visibilityState === 'visible') trigger();
  };
  win.addEventListener('focus', onFocus);
  doc.addEventListener('visibilitychange', onVisible);
  return () => {
    win.removeEventListener('focus', onFocus);
    doc.removeEventListener('visibilitychange', onVisible);
  };
}
