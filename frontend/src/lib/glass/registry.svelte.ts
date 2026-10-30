// Liquid glass registry: displacement maps shared by key, one SVG filter
// ("lens") per element. LiquidFilters renders `lenses`; the liquidGlass
// action adds, resizes and removes them.
import { refractBroken } from '../stores/glass';
import { generateLens } from './lensImage';
import type { FieldSpec } from './lensMap';
import { MAX_LENSES, type LensSpec } from './surfaces';

export type MapSpec = Omit<FieldSpec, 'lut'>;
export type MapGen = (spec: MapSpec, k: number) => string;
export type MapRequest = { key: string; spec: MapSpec; k: number };

export type Lens = {
  id: string;
  w: number;
  h: number;
  mapKey: string | null;
  url: string | null;
  /** feDisplacementMap scale (2·shift). */
  scale: number;
  frost: number;
  dispersion: boolean;
  mask: 'rim' | 'full';
};

type MapEntry = { url: string | null; refs: number; used: number; req: MapRequest };

/** Maps kept around with no lens using them. */
export const MAP_CACHE = 16;

type Schedule = (fn: () => void) => void;
const idle: Schedule = (fn) => {
  if (typeof requestIdleCallback === 'function') requestIdleCallback(() => fn(), { timeout: 200 });
  else setTimeout(fn, 0);
};

export class GlassRegistry {
  lenses = $state<Lens[]>([]);
  #maps = new Map<string, MapEntry>();
  #queue: string[] = [];
  #pumping = false;
  #seq = 0;
  #clock = 0;
  #listeners = new Set<() => void>();
  #gen: MapGen;
  #schedule: Schedule;
  #onBroken: () => void;

  constructor(gen: MapGen, opts: { schedule?: Schedule; onBroken?: () => void } = {}) {
    this.#gen = gen;
    this.#schedule = opts.schedule ?? idle;
    this.#onBroken = opts.onBroken ?? (() => refractBroken.set(true));
  }

  /** Called after any lens url changes (actions attach their filter then)
   *  and when a lens goes (an element refused at MAX_LENSES retries). */
  onChange(fn: () => void): () => void {
    this.#listeners.add(fn);
    return () => this.#listeners.delete(fn);
  }

  #emit() {
    for (const fn of [...this.#listeners]) fn();
  }

  map(key: string): Readonly<MapEntry> | undefined {
    return this.#maps.get(key);
  }

  get mapCount(): number {
    return this.#maps.size;
  }

  acquireMap(req: MapRequest): void {
    const e = this.#maps.get(req.key);
    if (e) {
      e.refs++;
      e.used = ++this.#clock;
      return;
    }
    this.#maps.set(req.key, { url: null, refs: 1, used: ++this.#clock, req });
    this.#enqueue(req.key);
  }

  releaseMap(key: string | null): void {
    if (!key) return;
    const e = this.#maps.get(key);
    if (!e) return;
    e.refs = Math.max(0, e.refs - 1);
    e.used = ++this.#clock;
    this.#evict();
  }

  /** Generate (or keep warm) a map without a lens using it. */
  prewarm(req: MapRequest): void {
    this.acquireMap(req);
    this.releaseMap(req.key);
  }

  #evict() {
    if (this.#maps.size <= MAP_CACHE) return;
    const idle = [...this.#maps.entries()].filter(([, e]) => e.refs === 0).sort((a, b) => a[1].used - b[1].used);
    for (const [key] of idle) {
      if (this.#maps.size <= MAP_CACHE) break;
      this.#maps.delete(key);
    }
  }

  #enqueue(key: string) {
    this.#queue.push(key);
    if (this.#pumping) return;
    this.#pumping = true;
    this.#schedule(() => this.#pump());
  }

  /** One map per idle slice. */
  #pump() {
    const key = this.#queue.shift();
    const e = key ? this.#maps.get(key) : undefined;
    if (e && e.url === null) {
      try {
        e.url = this.#gen(e.req.spec, e.req.k);
      } catch (err) {
        console.warn('liquid glass: map generation failed', err);
        this.#maps.delete(key!);
        this.#queue = [];
        this.#pumping = false;
        this.#onBroken();
        return;
      }
      let hit = false;
      for (const l of this.lenses) {
        if (l.mapKey === key) {
          l.url = e.url;
          hit = true;
        }
      }
      if (hit) this.#emit();
      this.#evict();
    }
    if (this.#queue.length) this.#schedule(() => this.#pump());
    else this.#pumping = false;
  }

  /** null when MAX_LENSES are in use (that element stays on the CSS tier). */
  addLens(spec: LensSpec): Lens | null {
    if (this.lenses.length >= MAX_LENSES) return null;
    const id = `lg-${++this.#seq}`;
    this.lenses.push({
      id,
      w: 1,
      h: 1,
      mapKey: null,
      url: null,
      scale: 2 * spec.shift,
      frost: spec.frost,
      dispersion: !!spec.dispersion,
      mask: spec.mask ?? 'rim',
    });
    return this.get(id)!;
  }

  get(id: string): Lens | undefined {
    return this.lenses.find((l) => l.id === id);
  }

  resizeLens(id: string, w: number, h: number): void {
    const l = this.get(id);
    if (!l) return;
    const rw = Math.max(1, Math.round(w));
    const rh = Math.max(1, Math.round(h));
    if (l.w !== rw) l.w = rw;
    if (l.h !== rh) l.h = rh;
  }

  /** Point a lens at another map: acquire the new one, then release the old.
   *  The old url stays until the new map is ready, so the lens never blinks. */
  setMap(id: string, req: MapRequest): void {
    const l = this.get(id);
    if (!l || l.mapKey === req.key) return;
    this.acquireMap(req);
    const old = l.mapKey;
    l.mapKey = req.key;
    this.releaseMap(old);
    const url = this.#maps.get(req.key)?.url;
    if (url && l.url !== url) {
      l.url = url;
      this.#emit();
    }
  }

  removeLens(id: string): void {
    const i = this.lenses.findIndex((l) => l.id === id);
    if (i < 0) return;
    const key = this.lenses[i].mapKey;
    this.lenses.splice(i, 1);
    this.releaseMap(key);
    this.#emit();
  }

  clear(): void {
    this.lenses.length = 0;
    this.#maps.clear();
    this.#queue = [];
  }
}

export const glassRegistry = new GlassRegistry(generateLens);
