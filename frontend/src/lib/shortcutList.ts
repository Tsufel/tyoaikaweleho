import type { CommandName } from './api/types';

// ── The shortcut list ───────────────────────────────────────────
// One table for the cheat sheet (? / F1), the Settings page and tooltips.

export interface ShortcutRow {
  /** Key combos, e.g. ['Enter', 'F2']; 'Click …' rows are not keys. */
  keys: string[];
  what: string;
  /** The command these keys run (a row without one is a mouse hint). */
  cmd?: CommandName;
}

export interface ShortcutGroup {
  title: 'Timer' | 'Shifts' | 'Navigation' | 'View' | 'Settings';
  rows: ShortcutRow[];
}

export const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: 'Timer',
    rows: [{ keys: ['F5'], what: 'Start / stop the timer', cmd: 'timer.toggle' }],
  },
  {
    title: 'Shifts',
    rows: [
      { keys: ['Ctrl+N'], what: 'Add a shift', cmd: 'entry.add' },
      { keys: ['Enter', 'F2'], what: 'Edit the selected shift', cmd: 'entry.edit' },
      { keys: ['Delete'], what: 'Delete the selected shift', cmd: 'entry.delete' },
      { keys: ['Ctrl+D'], what: 'Duplicate the selected shift to the next free day', cmd: 'entry.duplicate' },
      { keys: ['Ctrl+C'], what: 'Copy the selected shift as text', cmd: 'entry.copy' },
      { keys: ['Ctrl+F'], what: 'Filter the month', cmd: 'entry.filter' },
      { keys: ['Ctrl+Z'], what: 'Undo (while the note is shown)', cmd: 'undo' },
      { keys: ['Click a time'], what: 'Edit Time In / Time Out in place' },
      { keys: ['Ctrl+E'], what: 'Export to Excel', cmd: 'export' },
      { keys: ['Ctrl+I'], what: 'Import menu', cmd: 'import.menu' },
    ],
  },
  {
    title: 'Navigation',
    rows: [
      { keys: ['PgUp', 'Ctrl+←'], what: 'Previous month', cmd: 'month.prev' },
      { keys: ['PgDn', 'Ctrl+→'], what: 'Next month', cmd: 'month.next' },
      { keys: ['Ctrl+Home'], what: 'Go to the current month', cmd: 'month.current' },
      { keys: ['Ctrl+1'], what: 'Timer', cmd: 'view.timer' },
      { keys: ['Ctrl+2'], what: 'Shifts', cmd: 'view.shifts' },
      { keys: ['Ctrl+3'], what: 'Stats', cmd: 'view.stats' },
      { keys: ['Esc'], what: 'Leave Stats', cmd: 'stats.back' },
      { keys: ['Ctrl+K'], what: 'Find a command', cmd: 'palette.open' },
      { keys: ['?', 'F1'], what: 'This list of shortcuts', cmd: 'help.shortcuts' },
    ],
  },
  {
    title: 'View',
    rows: [
      { keys: ['Ctrl+=', 'Ctrl++'], what: 'Zoom in', cmd: 'zoom.in' },
      { keys: ['Ctrl+-'], what: 'Zoom out', cmd: 'zoom.out' },
      { keys: ['Ctrl+0'], what: 'Reset zoom to 100 %', cmd: 'zoom.reset' },
    ],
  },
  {
    title: 'Settings',
    rows: [
      { keys: ['Ctrl+,'], what: 'Open Settings', cmd: 'settings.open' },
      { keys: ['Ctrl+S'], what: 'Save Settings', cmd: 'settings.save' },
      { keys: ['Esc'], what: 'Leave Settings', cmd: 'settings.back' },
    ],
  },
];

/** Labels for tooltips / Kbd: each command's first key. */
export const SHORTCUT_LABELS: Partial<Record<CommandName, string>> = Object.fromEntries(
  SHORTCUT_GROUPS.flatMap((g) => g.rows).flatMap((r) => (r.cmd ? [[r.cmd, r.keys[0]]] : [])),
);
