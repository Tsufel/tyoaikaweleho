import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CommandName } from '../src/lib/api/types';

vi.mock('../src/lib/api/bridge', () => ({ api: {}, ready: Promise.resolve(), isMock: () => true }));

const { route } = await import('../src/lib/stores/app');
const { pushModal } = await import('../src/lib/stores/modals');
const sc = await import('../src/lib/shortcuts');
const { SHORTCUTS } = await import('../src/views/settings/settingsLogic');
const { createTypeahead, typeaheadIndex } = await import('../src/lib/ui/typeahead');

type KeyInit = { key: string; ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean; repeat?: boolean };
const ev = (init: KeyInit) => new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init });

/** Every key the app binds (one or more per command). */
const KEYS: KeyInit[] = [
  { key: 'F5' },
  { key: 'F1' },
  { key: '?', shiftKey: true },
  { key: 'n', ctrlKey: true },
  { key: 'e', ctrlKey: true },
  { key: 'i', ctrlKey: true },
  { key: ',', ctrlKey: true },
  { key: 's', ctrlKey: true },
  { key: 'z', ctrlKey: true },
  { key: 'ArrowLeft', ctrlKey: true },
  { key: 'ArrowRight', ctrlKey: true },
  { key: 'Home', ctrlKey: true },
  { key: '1', ctrlKey: true },
  { key: '2', ctrlKey: true },
  { key: '3', ctrlKey: true },
  { key: 'PageUp' },
  { key: 'PageDown' },
  { key: 'Enter' },
  { key: 'F2' },
  { key: '=', ctrlKey: true },
  { key: '+', ctrlKey: true, shiftKey: true },
  { key: '-', ctrlKey: true },
  { key: '0', ctrlKey: true },
  { key: 'k', ctrlKey: true },
  { key: 'Delete' },
  { key: 'Escape' },
];

describe('the shortcut table', () => {
  afterEach(() => route.set('main'));

  it('lists every command a key is bound to', () => {
    const listed = new Set(sc.SHORTCUT_GROUPS.flatMap((g) => g.rows).map((r) => r.cmd));
    const bound = new Set<CommandName>();
    for (const r of ['main', 'stats', 'settings'] as const) {
      route.set(r);
      for (const k of KEYS) {
        const b = sc.bindingFor(ev(k));
        if (b) bound.add(b.cmd);
      }
    }
    expect(bound.size).toBeGreaterThan(15);
    for (const cmd of bound) expect(listed, cmd).toContain(cmd);
  });

  it('Settings shows the same rows', () => {
    expect(SHORTCUTS).toEqual(sc.SHORTCUT_GROUPS.flatMap((g) => g.rows));
  });

  it('tooltip labels come from the table', () => {
    expect(sc.SHORTCUT_LABELS['month.prev']).toBe('PgUp');
    expect(sc.SHORTCUT_LABELS['help.shortcuts']).toBe('?');
    expect(sc.SHORTCUT_LABELS['view.stats']).toBe('Ctrl+3');
  });
});

describe('key bindings', () => {
  afterEach(() => route.set('main'));

  it('opens the cheat sheet on ? and F1 everywhere', () => {
    expect(sc.bindingFor(ev({ key: '?', shiftKey: true }))).toMatchObject({ cmd: 'help.shortcuts' });
    expect(sc.bindingFor(ev({ key: 'F1' }))?.routes).toEqual(['main', 'stats', 'settings']);
    expect(sc.bindingFor(ev({ key: '?', ctrlKey: true }))).toBeNull();
  });

  it('maps Ctrl+1/2/3 to the views', () => {
    expect(sc.bindingFor(ev({ key: '1', ctrlKey: true }))?.cmd).toBe('view.timer');
    expect(sc.bindingFor(ev({ key: '2', ctrlKey: true }))?.cmd).toBe('view.shifts');
    expect(sc.bindingFor(ev({ key: '3', ctrlKey: true }))?.cmd).toBe('view.stats');
  });

  it('Escape leaves Stats or Settings depending on the route', () => {
    route.set('stats');
    expect(sc.bindingFor(ev({ key: 'Escape' }))?.cmd).toBe('stats.back');
    route.set('settings');
    expect(sc.bindingFor(ev({ key: 'Escape' }))?.cmd).toBe('settings.back');
  });
});

describe('the global key handler', () => {
  let stop: () => void;
  let offs: (() => void)[] = [];
  const seen: string[] = [];
  const bind = (name: CommandName) => offs.push(sc.registerCommand(name, () => void seen.push(name)));

  beforeEach(() => {
    stop = sc.startShortcuts();
    seen.length = 0;
    for (const n of ['help.shortcuts', 'view.stats', 'stats.back', 'wizard.secret'] as CommandName[]) bind(n);
  });
  afterEach(() => {
    stop();
    offs.forEach((f) => f());
    offs = [];
    route.set('main');
    document.body.innerHTML = '';
  });

  it('runs a view switch and the cheat sheet', () => {
    window.dispatchEvent(ev({ key: '3', ctrlKey: true }));
    window.dispatchEvent(ev({ key: '?', shiftKey: true }));
    expect(seen).toEqual(['view.stats', 'help.shortcuts']);
  });

  it('ignores ? while typing, but not F1', () => {
    const input = document.createElement('input');
    document.body.append(input);
    input.focus();
    input.dispatchEvent(ev({ key: '?', shiftKey: true }));
    expect(seen).toEqual([]);
    input.dispatchEvent(ev({ key: 'F1' }));
    expect(seen).toEqual(['help.shortcuts']);
  });

  it('does nothing while a modal is open', () => {
    const m = pushModal(() => {});
    window.dispatchEvent(ev({ key: 'F1' }));
    window.dispatchEvent(ev({ key: '1', ctrlKey: true }));
    m.release();
    expect(seen).toEqual([]);
  });

  it('Escape on Stats goes back', () => {
    route.set('stats');
    window.dispatchEvent(ev({ key: 'Escape' }));
    expect(seen).toEqual(['stats.back']);
  });

  it('the Konami code runs the secret once', () => {
    for (const key of sc.KONAMI) window.dispatchEvent(ev({ key }));
    expect(seen).toEqual(['wizard.secret']);
  });

  it('the Konami code does not count keys typed into a field', () => {
    const input = document.createElement('input');
    document.body.append(input);
    input.focus();
    for (const key of sc.KONAMI) input.dispatchEvent(ev({ key }));
    expect(seen).toEqual([]);
  });
});

describe('feedKonami', () => {
  it('matches the code at the end of the buffer only', () => {
    let buf: string[] = [];
    let hits = 0;
    for (const key of ['x', 'ArrowUp', ...sc.KONAMI]) {
      const r = sc.feedKonami(buf, key);
      buf = r.buf;
      if (r.hit) hits++;
    }
    expect(hits).toBe(1);
    expect(buf).toEqual([]);
  });

  it('accepts a capital B and A', () => {
    let buf: string[] = [];
    let hit = false;
    for (const key of [...sc.KONAMI.slice(0, 8), 'B', 'A']) ({ buf, hit } = sc.feedKonami(buf, key));
    expect(hit).toBe(true);
  });

  it('keeps no more than ten keys', () => {
    let buf: string[] = [];
    for (let i = 0; i < 50; i++) buf = sc.feedKonami(buf, 'x').buf;
    expect(buf).toHaveLength(10);
  });
});

describe('menu typeahead', () => {
  const labels = ['Export', 'Edit', 'Delete', 'Duplicate'];

  it('jumps to the next item starting with a letter, wrapping', () => {
    expect(typeaheadIndex(labels, 0, 'd')).toBe(2);
    expect(typeaheadIndex(labels, 2, 'd')).toBe(3);
    expect(typeaheadIndex(labels, 3, 'd')).toBe(2);
    expect(typeaheadIndex(labels, 1, 'e')).toBe(0);
  });

  it('a longer buffer narrows from the current item', () => {
    expect(typeaheadIndex(labels, 2, 'du')).toBe(3);
    expect(typeaheadIndex(labels, 0, 'ed')).toBe(1);
    expect(typeaheadIndex(labels, 0, 'zz')).toBe(-1);
  });

  it('a repeated letter cycles', () => {
    expect(typeaheadIndex(labels, 2, 'dd')).toBe(3);
  });

  it('the buffer clears after a pause', () => {
    let now = 0;
    const typed = createTypeahead(500, () => now);
    expect(typed('d')).toBe('d');
    now = 200;
    expect(typed('u')).toBe('du');
    now = 900;
    expect(typed('e')).toBe('e');
  });
});
