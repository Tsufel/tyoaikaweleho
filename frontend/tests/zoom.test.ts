import { afterEach, describe, expect, it, vi } from 'vitest';
import { applyZoom, cleanZoom, layoutRect, stepZoom, uiScale, ZOOM_LEVELS } from '../src/lib/zoom';

vi.mock('../src/lib/api/bridge', () => ({ api: {}, ready: Promise.resolve(), isMock: () => true }));

const { route } = await import('../src/lib/stores/app');
const { pushModal } = await import('../src/lib/stores/modals');
const sc = await import('../src/lib/shortcuts');

afterEach(() => applyZoom(100));

describe('zoom levels', () => {
  it('match storage.ZOOM_LEVELS', () => {
    expect(ZOOM_LEVELS).toEqual([80, 90, 100, 110, 120, 130, 140, 150]);
  });

  it('cleanZoom keeps a level and turns anything else into 100', () => {
    expect(cleanZoom(120)).toBe(120);
    for (const bad of [undefined, null, '110', 115, 200, NaN]) expect(cleanZoom(bad)).toBe(100);
  });

  it('stepZoom moves one level and stops at the ends', () => {
    expect(stepZoom(100, 1)).toBe(110);
    expect(stepZoom(100, -1)).toBe(90);
    expect(stepZoom(150, 1)).toBe(150);
    expect(stepZoom(80, -1)).toBe(80);
    expect(stepZoom(999, 1)).toBe(110); // a bad value counts as 100
  });
});

describe('applyZoom', () => {
  it('sets CSS zoom on the root, and clears it at 100 %', () => {
    const root = document.createElement('div');
    applyZoom(125, root); // not a level: 100
    expect(root.style.zoom).toBe('');
    applyZoom(130, root);
    expect(root.style.zoom).toBe('1.3');
    expect(uiScale()).toBeCloseTo(1.3);
    applyZoom(100, root);
    expect(root.style.zoom).toBe('');
    expect(uiScale()).toBe(1);
  });

  it('layoutRect turns visual px into layout px', () => {
    applyZoom(150, document.createElement('div'));
    const r = layoutRect(new DOMRect(30, 60, 150, 15));
    expect(r).toEqual({ left: 20, top: 40, right: 120, bottom: 50, width: 100, height: 10 });
  });
});

describe('zoom and palette keys', () => {
  const ev = (key: string, init: KeyboardEventInit = {}) => new KeyboardEvent('keydown', { key, ctrlKey: true, bubbles: true, cancelable: true, ...init });
  let offs: (() => void)[] = [];
  const seen: string[] = [];
  let stop: () => void = () => {};

  afterEach(() => {
    stop();
    offs.forEach((f) => f());
    offs = [];
    seen.length = 0;
    route.set('main');
    document.body.innerHTML = '';
  });

  function setup() {
    stop = sc.startShortcuts();
    for (const n of ['zoom.in', 'zoom.out', 'zoom.reset', 'palette.open'] as const) {
      offs.push(sc.registerCommand(n, () => void seen.push(n)));
    }
  }

  it('Ctrl+= / Ctrl++ / Ctrl+- / Ctrl+0 zoom on every route, and stop the browser zoom', () => {
    setup();
    for (const r of ['main', 'stats', 'settings'] as const) {
      route.set(r);
      seen.length = 0;
      const e = ev('=');
      window.dispatchEvent(e);
      expect(e.defaultPrevented).toBe(true);
      window.dispatchEvent(ev('+', { shiftKey: true })); // US keyboard
      window.dispatchEvent(ev('+')); // Finnish keyboard
      window.dispatchEvent(ev('-'));
      window.dispatchEvent(ev('0'));
      expect(seen).toEqual(['zoom.in', 'zoom.in', 'zoom.in', 'zoom.out', 'zoom.reset']);
    }
  });

  it('zoom works while typing and inside a modal; the palette does not open over a modal', () => {
    setup();
    const input = document.createElement('input');
    document.body.append(input);
    input.focus();
    input.dispatchEvent(ev('-'));
    const m = pushModal(() => {});
    window.dispatchEvent(ev('='));
    window.dispatchEvent(ev('k'));
    m.release();
    window.dispatchEvent(ev('k'));
    expect(seen).toEqual(['zoom.out', 'zoom.in', 'palette.open']);
  });

  it('holding a zoom key repeats it; Ctrl+K does not', () => {
    setup();
    window.dispatchEvent(ev('=', { repeat: true }));
    window.dispatchEvent(ev('k', { repeat: true }));
    expect(seen).toEqual(['zoom.in']);
  });
});
