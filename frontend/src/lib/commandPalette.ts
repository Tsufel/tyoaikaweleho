import { get } from 'svelte/store';
import type { CommandName } from './api/types';
import { hasCommand } from './shortcuts';
import { SHORTCUT_LABELS } from './shortcutList';
import { route } from './stores/app';
import { month } from './stores/entries';
import { undoAvailable } from './stores/toasts';

// ── The command palette (Ctrl+K) ────────────────────────────────
// Commands from the shortcut registry that make sense without a selected
// shift. A command is offered only on its routes, while something has
// registered a handler for it, and while its `when` holds.

type Route = 'main' | 'stats' | 'settings';

export interface PaletteItem {
  cmd: CommandName;
  label: string;
  /** Extra words the filter matches (not shown). */
  keywords?: string;
  /** Routes it is offered on (default: all). */
  routes?: Route[];
  when?: () => boolean;
}

const MAIN: Route[] = ['main'];
const MAIN_STATS: Route[] = ['main', 'stats'];

export const PALETTE_ITEMS: PaletteItem[] = [
  { cmd: 'timer.toggle', label: 'Start or stop the timer', keywords: 'clock shift', routes: MAIN_STATS },
  { cmd: 'entry.add', label: 'Add a shift', keywords: 'new entry hours', routes: MAIN },
  // the filter box only shows when the month has shifts
  { cmd: 'entry.filter', label: 'Filter the month', keywords: 'search find', routes: MAIN, when: () => (get(month)?.entries.length ?? 0) > 0 },
  { cmd: 'undo', label: 'Undo', keywords: 'revert', routes: MAIN_STATS, when: () => get(undoAvailable) },
  { cmd: 'export', label: 'Export to Excel', keywords: 'xlsx spreadsheet save', routes: MAIN },
  { cmd: 'import.menu', label: 'Import shifts', keywords: 'excel image open', routes: MAIN },
  { cmd: 'month.prev', label: 'Previous month', keywords: 'back', routes: MAIN },
  { cmd: 'month.next', label: 'Next month', keywords: 'forward', routes: MAIN },
  { cmd: 'month.current', label: 'Go to the current month', keywords: 'today this', routes: MAIN },
  { cmd: 'view.timer', label: 'Show the Timer', keywords: 'view', routes: MAIN_STATS },
  { cmd: 'view.shifts', label: 'Show Shifts', keywords: 'view list', routes: MAIN_STATS },
  { cmd: 'view.stats', label: 'Show Stats', keywords: 'view charts statistics', routes: MAIN_STATS },
  { cmd: 'stats.back', label: 'Leave Stats', keywords: 'close back', routes: ['stats'] },
  { cmd: 'settings.open', label: 'Open Settings', keywords: 'preferences options', routes: MAIN_STATS },
  { cmd: 'settings.save', label: 'Save Settings', routes: ['settings'] },
  { cmd: 'settings.back', label: 'Leave Settings', keywords: 'close back', routes: ['settings'] },
  { cmd: 'zoom.in', label: 'Zoom in', keywords: 'bigger larger text size' },
  { cmd: 'zoom.out', label: 'Zoom out', keywords: 'smaller text size' },
  { cmd: 'zoom.reset', label: 'Reset zoom to 100 %', keywords: 'actual size' },
  { cmd: 'help.shortcuts', label: 'Show keyboard shortcuts', keywords: 'keys help cheat sheet' },
];

/** The items that can run right now, in list order. */
export function availableItems(items: PaletteItem[] = PALETTE_ITEMS, r: Route = get(route)): PaletteItem[] {
  return items.filter((it) => (it.routes ?? ['main', 'stats', 'settings']).includes(r) && hasCommand(it.cmd) && (it.when?.() ?? true));
}

/** The shortcut shown beside an item. */
export function itemKeys(it: PaletteItem): string | undefined {
  return SHORTCUT_LABELS[it.cmd];
}

const isWordStart = (t: string, i: number) => i === 0 || /[\s\-/]/.test(t[i - 1]);

/** How well `query` matches `text`, or null for no match. Higher is better:
 *  a whole-word or prefix hit beats a substring, which beats the letters in
 *  order ("ex xl" finds "Export to Excel"). Case-insensitive. */
export function fuzzyScore(query: string, text: string): number | null {
  const q = query.trim().toLowerCase().replace(/\s+/g, ' ');
  if (!q) return 0;
  const t = text.toLowerCase();
  const at = t.indexOf(q);
  if (at >= 0) return 1000 - at + (isWordStart(t, at) ? 500 : 0);
  // every word of the query, in order, as a run of letters in order
  let score = 0;
  let from = 0;
  for (const word of q.split(' ')) {
    let prev = -2;
    for (const ch of word) {
      const j = t.indexOf(ch, from);
      if (j < 0) return null;
      score += (j === prev + 1 ? 6 : 0) + (isWordStart(t, j) ? 4 : 0) - Math.min(j - from, 10) * 0.1;
      prev = j;
      from = j + 1;
    }
  }
  return score;
}

/** The items matching `query`, best first (ties keep list order). */
export function filterItems(items: PaletteItem[], query: string): PaletteItem[] {
  if (!query.trim()) return items;
  const scored: { it: PaletteItem; s: number; i: number }[] = [];
  items.forEach((it, i) => {
    const label = fuzzyScore(query, it.label);
    const words = it.keywords ? fuzzyScore(query, `${it.label} ${it.keywords}`) : null;
    // a hit in the label counts more than one that needs the keywords
    const s = label !== null ? label + 100 : words;
    if (s !== null) scored.push({ it, s, i });
  });
  return scored.sort((a, b) => b.s - a.s || a.i - b.i).map((x) => x.it);
}
