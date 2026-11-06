import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/lib/api/bridge', () => ({ api: {}, ready: Promise.resolve(), isMock: () => true }));

const { availableItems, filterItems, fuzzyScore, itemKeys, PALETTE_ITEMS } = await import('../src/lib/commandPalette');
const { registerCommand } = await import('../src/lib/shortcuts');
const { SHORTCUT_GROUPS } = await import('../src/lib/shortcutList');
const { toast, clearToasts } = await import('../src/lib/stores/toasts');

let offs: (() => void)[] = [];
afterEach(() => {
  offs.forEach((f) => f());
  offs = [];
  clearToasts();
});
const bindAll = () => {
  for (const it of PALETTE_ITEMS) offs.push(registerCommand(it.cmd, () => {}));
};

describe('fuzzyScore', () => {
  it('matches case-insensitively; an empty query matches everything', () => {
    expect(fuzzyScore('', 'Add a shift')).toBe(0);
    expect(fuzzyScore('SHIFT', 'Add a shift')).not.toBeNull();
  });

  it('finds the letters in order, and nothing out of order', () => {
    expect(fuzzyScore('ex xl', 'Export to Excel')).not.toBeNull();
    expect(fuzzyScore('expt', 'Export to Excel')).not.toBeNull();
    expect(fuzzyScore('lecxe', 'Export to Excel')).toBeNull();
    expect(fuzzyScore('zz', 'Zoom in')).toBeNull();
  });

  it('a word start beats a match inside a word, which beats scattered letters', () => {
    const start = fuzzyScore('set', 'Open Settings')!;
    const inside = fuzzyScore('ett', 'Open Settings')!;
    const scattered = fuzzyScore('opst', 'Open Settings')!;
    expect(start).toBeGreaterThan(inside);
    expect(inside).toBeGreaterThan(scattered);
  });
});

describe('filterItems', () => {
  it('keeps list order without a query', () => {
    expect(filterItems(PALETTE_ITEMS, '  ')).toEqual(PALETTE_ITEMS);
  });

  it('puts the best match first and drops non-matches', () => {
    const r = filterItems(PALETTE_ITEMS, 'zoom').map((i) => i.cmd);
    expect(r.slice(0, 3).sort()).toEqual(['zoom.in', 'zoom.out', 'zoom.reset']);
    expect(filterItems(PALETTE_ITEMS, 'export')[0].cmd).toBe('export');
    expect(filterItems(PALETTE_ITEMS, 'qqqq')).toEqual([]);
  });

  it('matches hidden keywords, below label matches', () => {
    expect(filterItems(PALETTE_ITEMS, 'spreadsheet').map((i) => i.cmd)).toEqual(['export']);
    const r = filterItems(PALETTE_ITEMS, 'back').map((i) => i.cmd);
    expect(r).toContain('stats.back');
  });
});

describe('availableItems', () => {
  it('lists only commands with a handler', () => {
    expect(availableItems(PALETTE_ITEMS, 'main')).toEqual([]);
    offs.push(registerCommand('entry.add', () => {}));
    expect(availableItems(PALETTE_ITEMS, 'main').map((i) => i.cmd)).toEqual(['entry.add']);
  });

  it('keeps to each command’s routes', () => {
    bindAll();
    const settings = availableItems(PALETTE_ITEMS, 'settings').map((i) => i.cmd);
    expect(settings).toContain('settings.save');
    expect(settings).toContain('zoom.in');
    expect(settings).not.toContain('entry.add');
    expect(settings).not.toContain('settings.open');
    const stats = availableItems(PALETTE_ITEMS, 'stats').map((i) => i.cmd);
    expect(stats).toContain('stats.back');
    expect(stats).not.toContain('settings.save');
  });

  it('offers Undo only while there is something to undo', () => {
    bindAll();
    expect(availableItems(PALETTE_ITEMS, 'main').map((i) => i.cmd)).not.toContain('undo');
    toast('Shift deleted', { action: () => {}, label: 'Undo' });
    expect(availableItems(PALETTE_ITEMS, 'main').map((i) => i.cmd)).toContain('undo');
  });
});

describe('the palette list', () => {
  it('names each command once', () => {
    const cmds = PALETTE_ITEMS.map((i) => i.cmd);
    expect(new Set(cmds).size).toBe(cmds.length);
  });

  it('shows the shortcut from the shortcut table', () => {
    const listed = new Set(SHORTCUT_GROUPS.flatMap((g) => g.rows).map((r) => r.cmd));
    for (const it of PALETTE_ITEMS) expect(listed, it.cmd).toContain(it.cmd);
    expect(itemKeys(PALETTE_ITEMS.find((i) => i.cmd === 'zoom.in')!)).toBe('Ctrl+=');
  });
});
