import { get } from 'svelte/store';
import type { CommandName } from './api/types';
import { route } from './stores/app';
import { isModalOpen } from './stores/modals';
import { undoAvailable } from './stores/toasts';

type Handler = () => void | Promise<void>;

const commands = new Map<CommandName, Handler[]>();

/** Bind a command; the most recently registered handler wins. Returns unregister. */
export function registerCommand(name: CommandName, fn: Handler): () => void {
  const list = commands.get(name) ?? [];
  list.push(fn);
  commands.set(name, list);
  return () => {
    const l = commands.get(name);
    if (!l) return;
    const i = l.lastIndexOf(fn);
    if (i >= 0) l.splice(i, 1);
  };
}

export function hasCommand(name: CommandName): boolean {
  return (commands.get(name)?.length ?? 0) > 0;
}

/** Run a command (also for buttons/menus). False when nothing is bound. */
export function runCommand(name: CommandName): boolean {
  const l = commands.get(name);
  const fn = l?.[l.length - 1];
  if (!fn) return false;
  void fn();
  return true;
}

/** Focus is in a text field (v1.3 _TEXT_CLASSES: Entry/Text/Combobox/Spinbox). */
export function isTyping(target: EventTarget | null = document.activeElement): boolean {
  const el = target as HTMLElement | null;
  if (!el || !el.tagName) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag !== 'INPUT') return false;
  const type = (el as HTMLInputElement).type;
  return !['button', 'checkbox', 'radio', 'range', 'submit', 'reset', 'color', 'file'].includes(type);
}

const ACTIVATORS =
  'button, a[href], [role="button"], [role="menuitem"], [role="option"], [role="tab"], [role="switch"], [role="radio"], summary';
const isActivator = (t: EventTarget | null) => !!(t as HTMLElement | null)?.closest?.(ACTIVATORS);

interface Binding {
  cmd: CommandName;
  /** Allowed while focus is in a text field. */
  typing?: boolean;
  /** Routes it works on (default: main). */
  routes?: string[];
  /** Skip while a button etc. has focus (Enter would activate it). */
  notOnActivator?: boolean;
  /** Only with focus in the shifts table (v1.3 bound these on the Treeview). */
  inTable?: boolean;
  when?: () => boolean;
  /** Prevent the browser default even when gated off (Ctrl+N opens a window, F5 reloads). */
  alwaysPrevent?: boolean;
}

const ALL_ROUTES = ['main', 'stats', 'settings'];

/** The command a key press maps to, with its gates (exported for tests). */
export function bindingFor(e: KeyboardEvent): Binding | null {
  const ctrl = e.ctrlKey || e.metaKey;
  if (e.altKey) return null;
  const k = e.key;
  if (!ctrl && !e.shiftKey && k === 'F5') {
    return { cmd: 'timer.toggle', typing: true, routes: ['main', 'stats'], alwaysPrevent: true };
  }
  // the cheat sheet: '?' is Shift+/ (or Shift++ on a Finnish keyboard)
  if (!ctrl && k === '?') return { cmd: 'help.shortcuts', routes: ALL_ROUTES };
  if (!ctrl && !e.shiftKey && k === 'F1') {
    return { cmd: 'help.shortcuts', typing: true, routes: ALL_ROUTES, alwaysPrevent: true };
  }
  if (ctrl && !e.shiftKey) {
    switch (k.toLowerCase()) {
      case 'n': return { cmd: 'entry.add', typing: true, alwaysPrevent: true };
      case 'e': return { cmd: 'export', typing: true, alwaysPrevent: true };
      case 'i': return { cmd: 'import.menu', typing: true, alwaysPrevent: true };
      case ',': return { cmd: 'settings.open', typing: true, routes: ['main', 'stats'], alwaysPrevent: true };
      case 's': return { cmd: 'settings.save', typing: true, routes: ['settings'], alwaysPrevent: true };
      case 'z': return { cmd: 'undo', routes: ['main', 'stats'], when: () => get(undoAvailable) };
      case 'd': return { cmd: 'entry.duplicate' };
      case 'f': return { cmd: 'entry.filter', typing: true };
      case 'c': return { cmd: 'entry.copy', inTable: true, when: () => !window.getSelection()?.toString() };
      case 'arrowleft':
      case 'pageup': return { cmd: 'month.prev' };
      case 'arrowright':
      case 'pagedown': return { cmd: 'month.next' };
      case 'home': return { cmd: 'month.current' };
      case '1': return { cmd: 'view.timer', routes: ['main', 'stats'] };
      case '2': return { cmd: 'view.shifts', routes: ['main', 'stats'] };
      case '3': return { cmd: 'view.stats', routes: ['main', 'stats'] };
    }
    return null;
  }
  if (ctrl || e.shiftKey) return null;
  switch (k) {
    case 'PageUp': return { cmd: 'month.prev' };
    case 'PageDown': return { cmd: 'month.next' };
    case 'Escape':
      return get(route) === 'stats'
        ? { cmd: 'stats.back', routes: ['stats'] }
        : { cmd: 'settings.back', typing: true, routes: ['settings'] };
    case 'Enter': return { cmd: 'entry.edit', notOnActivator: true, inTable: true };
    case 'F2': return { cmd: 'entry.edit', inTable: true };
    case 'Delete': return { cmd: 'entry.delete', inTable: true };
  }
  return null;
}

// ── Konami code ─────────────────────────────────────────────────

export const KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];

/** Add a key to the rolling buffer (the last KONAMI.length keys). True in
 *  `hit` when the buffer now ends with the code; the buffer then restarts. */
export function feedKonami(buf: string[], key: string): { buf: string[]; hit: boolean } {
  const k = key.length === 1 ? key.toLowerCase() : key;
  const next = [...buf, k].slice(-KONAMI.length);
  const hit = next.length === KONAMI.length && next.every((x, i) => x === KONAMI[i]);
  return { buf: hit ? [] : next, hit };
}

let konami: string[] = [];

function trackKonami(e: KeyboardEvent): void {
  if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || isModalOpen() || isTyping(e.target)) {
    konami = [];
    return;
  }
  if (e.key === 'Shift') return;
  const r = feedKonami(konami, e.key);
  konami = r.buf;
  if (r.hit) runCommand('wizard.secret');
}

function onKeyDown(e: KeyboardEvent): void {
  if (e.isComposing) return;
  trackKonami(e);
  const b = bindingFor(e);
  if (!b) return;
  // a focused component already handled the key
  if (e.defaultPrevented) return;
  if (b.alwaysPrevent) e.preventDefault();
  if (isModalOpen()) return; // the modal owns the keyboard
  if (!b.typing && isTyping(e.target)) return;
  if (b.notOnActivator && isActivator(e.target)) return;
  if (b.inTable && !(e.target instanceof Element && e.target.closest('[data-entries-table]'))) return;
  if (!(b.routes ?? ['main']).includes(get(route))) return;
  if (b.when && !b.when()) return;
  if (e.repeat && b.cmd !== 'month.prev' && b.cmd !== 'month.next') return;
  if (runCommand(b.cmd)) e.preventDefault();
}

let installed = false;

/** Install the global key handler (App does this once). */
export function startShortcuts(): () => void {
  if (installed) return () => {};
  installed = true;
  window.addEventListener('keydown', onKeyDown);
  return () => {
    installed = false;
    window.removeEventListener('keydown', onKeyDown);
  };
}

/** The shortcut table (cheat sheet, Settings, tooltip labels). */
export { SHORTCUT_GROUPS, SHORTCUT_LABELS, type ShortcutGroup, type ShortcutRow } from './shortcutList';
