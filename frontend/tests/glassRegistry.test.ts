import { get } from 'svelte/store';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GlassRegistry, MAP_CACHE, type MapRequest } from '../src/lib/glass/registry.svelte';
import { MAX_LENSES, SURFACES } from '../src/lib/glass/surfaces';
import { refractBroken } from '../src/lib/stores/glass';

function setup(gen = (s: MapRequest['spec']) => `data:${s.w}x${s.h}`, onBroken?: () => void) {
  const jobs: (() => void)[] = [];
  const reg = new GlassRegistry(gen, { schedule: (fn) => jobs.push(fn), ...(onBroken ? { onBroken } : {}) });
  const flush = () => {
    while (jobs.length) jobs.shift()!();
  };
  return { reg, flush, jobs };
}

const req = (key: string, w = 100, h = 40): MapRequest => ({
  key,
  spec: { w, h, r: 20, b: 10, shift: 10 },
  k: 1,
});

afterEach(() => refractBroken.set(false));

describe('GlassRegistry maps', () => {
  it('shares one map per key', () => {
    const { reg } = setup();
    reg.acquireMap(req('a'));
    reg.acquireMap(req('a'));
    expect(reg.mapCount).toBe(1);
    expect(reg.map('a')?.refs).toBe(2);
  });

  it('keeps released maps cached', () => {
    const { reg, flush } = setup();
    reg.acquireMap(req('a'));
    flush();
    reg.releaseMap('a');
    expect(reg.map('a')?.refs).toBe(0);
    expect(reg.map('a')?.url).toBe('data:100x40');
  });

  it('evicts only unused maps, oldest first, past the cache size', () => {
    const { reg } = setup();
    reg.acquireMap(req('held'));
    for (let i = 0; i < MAP_CACHE; i++) reg.prewarm(req(`m${i}`));
    expect(reg.mapCount).toBe(MAP_CACHE);
    expect(reg.map('held')).toBeDefined();
    expect(reg.map('m0')).toBeUndefined();
    expect(reg.map('m1')).toBeDefined();
    reg.prewarm(req('m1')); // touch: m1 becomes newest
    reg.prewarm(req('late'));
    expect(reg.map('m1')).toBeDefined();
    expect(reg.map('m2')).toBeUndefined();
    expect(reg.map('held')?.refs).toBe(1);
  });

  it('generates maps asynchronously and notifies listeners', () => {
    const gen = vi.fn((s: MapRequest['spec']) => `data:${s.w}`);
    const { reg, flush } = setup(gen);
    const lens = reg.addLens(SURFACES.topbar)!;
    const seen = vi.fn();
    reg.onChange(seen);
    reg.setMap(lens.id, req('a'));
    expect(reg.get(lens.id)?.url).toBeNull();
    expect(gen).not.toHaveBeenCalled();
    flush();
    expect(gen).toHaveBeenCalledTimes(1);
    expect(reg.get(lens.id)?.url).toBe('data:100');
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it('keeps the old url until the next map is ready', () => {
    const { reg, flush } = setup();
    const lens = reg.addLens(SURFACES.topbar)!;
    reg.setMap(lens.id, req('a'));
    flush();
    reg.setMap(lens.id, req('b', 120));
    expect(reg.get(lens.id)?.url).toBe('data:100x40');
    expect(reg.map('a')?.refs).toBe(0);
    flush();
    expect(reg.get(lens.id)?.url).toBe('data:120x40');
  });

  it('reports a throwing generator (default: refractBroken)', () => {
    const boom = () => {
      throw new Error('no canvas');
    };
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const onBroken = vi.fn();
    const a = setup(boom, onBroken);
    a.reg.acquireMap(req('a'));
    a.flush();
    expect(onBroken).toHaveBeenCalledTimes(1);
    expect(a.reg.map('a')).toBeUndefined();

    const b = setup(boom);
    b.reg.acquireMap(req('a'));
    b.flush();
    expect(get(refractBroken)).toBe(true);
    warn.mockRestore();
  });
});

describe('GlassRegistry lenses', () => {
  it('refuses lenses past MAX_LENSES', () => {
    const { reg } = setup();
    for (let i = 0; i < MAX_LENSES; i++) expect(reg.addLens(SURFACES.toast)).not.toBeNull();
    expect(reg.addLens(SURFACES.toast)).toBeNull();
    reg.removeLens(reg.lenses[0].id);
    expect(reg.addLens(SURFACES.toast)).not.toBeNull();
  });

  it('tells listeners when a slot frees up', () => {
    const { reg } = setup();
    const l = reg.addLens(SURFACES.toast)!;
    const seen = vi.fn();
    reg.onChange(seen);
    reg.removeLens(l.id);
    expect(seen).toHaveBeenCalledTimes(1);
    reg.removeLens(l.id); // unknown id: no event
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it('copies the surface spec into the lens', () => {
    const { reg } = setup();
    const l = reg.addLens({ ...SURFACES.modal, dispersion: true })!;
    expect(l).toMatchObject({ scale: 36, frost: 14, dispersion: true, mask: 'rim', url: null });
    reg.resizeLens(l.id, 320.4, 199.6);
    expect(reg.get(l.id)).toMatchObject({ w: 320, h: 200 });
  });

  it('releases the map when a lens goes', () => {
    const { reg } = setup();
    const l = reg.addLens(SURFACES.toast)!;
    reg.setMap(l.id, req('a'));
    reg.removeLens(l.id);
    expect(reg.lenses).toHaveLength(0);
    expect(reg.map('a')?.refs).toBe(0);
  });

  it('clear() empties lenses and maps', () => {
    const { reg, flush } = setup();
    const l = reg.addLens(SURFACES.toast)!;
    reg.setMap(l.id, req('a'));
    reg.prewarm(req('b'));
    flush();
    reg.clear();
    expect(reg.lenses).toHaveLength(0);
    expect(reg.mapCount).toBe(0);
  });
});
