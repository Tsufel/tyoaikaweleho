// Liquid glass action: gives an element its own SVG refraction lens while
// the glass mode is 'refract'. In 'css' and 'off' it only holds one store
// subscription; the CSS-tier look comes from liquid.css alone.
//
//   <header class="topbar glass lg-float" use:liquidGlass={'topbar'}>
//   <span class="pill" use:liquidGlass={{ key: 'pill', active: moving, onlens }}>
import { tick, untrack } from 'svelte';
import type { Action } from 'svelte/action';
import { get } from 'svelte/store';
import { glassLive, glassMode, type GlassMode } from '../stores/glass';
import { mapKey, mapScale, type FieldSpec } from './lensMap';
import { lightDriver } from './light';
import { glassRegistry, type Lens, type MapRequest } from './registry.svelte';
import { SURFACES, type LensSpec, type SurfaceKey } from './surfaces';

export type LiquidGlassParam =
  | SurfaceKey
  | {
      key: SurfaceKey;
      active?: boolean;
      /** Told when the element's own refraction lens attaches (true) or goes (false). */
      onlens?: (on: boolean) => void;
    };

/** Lens id per attached node (pulseLens). */
const attachedIds = new WeakMap<Element, string>();
/** A pulse asked for just before the lens attached (the pill's pointerdown). */
const pendingPulse = new WeakMap<Element, { factor: number; ms: number; at: number }>();
/** Running scale tween per lens id. */
const tweens = new Map<string, number>();

const SETTLE_MS = 120;
/** A transient lens (the moving thumb) follows its animating size at most this often. */
const TRANSIENT_RESIZE_MS = 100;
const MATERIALIZE_MS = 240;
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/** The feDisplacementMap node(s) of a lens with their scale factors. */
function scaleNodes(id: string): [Element, number][] {
  const one = document.getElementById(`${id}-d`);
  if (one) return [[one, 1]];
  const out: [Element, number][] = [];
  for (const c of ['r', 'g', 'b']) {
    const el = document.getElementById(`${id}-d${c}`);
    if (el) out.push([el, Number(el.getAttribute('data-f') ?? 1) || 1]);
  }
  return out;
}

/** Tween a lens's displacement as `base · curve(t)` (written straight to the
 *  attribute, not through $state). The curve must end at 1. */
function animateScale(id: string, curve: (t: number) => number, ms: number): void {
  const lens = glassRegistry.get(id);
  const nodes = scaleNodes(id);
  if (!lens || !nodes.length) return;
  cancelAnimationFrame(tweens.get(id) ?? 0);
  const base = lens.scale;
  const write = (m: number) => {
    for (const [el, f] of nodes) el.setAttribute('scale', String(Math.round(base * f * m * 100) / 100));
  };
  const t0 = performance.now();
  const frame = (now: number) => {
    const t = Math.min(1, (now - t0) / ms);
    write(t >= 1 ? 1 : curve(t));
    if (t < 1) tweens.set(id, requestAnimationFrame(frame));
    else tweens.delete(id);
  };
  write(curve(0));
  tweens.set(id, requestAnimationFrame(frame));
}

function stopTween(id: string): void {
  cancelAnimationFrame(tweens.get(id) ?? 0);
  tweens.delete(id);
}

function pulse(id: string, factor: number, ms: number): void {
  animateScale(id, (t) => 1 + (factor - 1) * Math.sin(Math.PI * t), ms);
}

/** Briefly over-bend a node's lens (the Segmented thumb on press). */
export function pulseLens(node: Element | null | undefined, factor = 1.3, ms = 140): void {
  if (!node || !get(glassLive)) return;
  const id = attachedIds.get(node);
  if (id) pulse(id, factor, ms);
  else pendingPulse.set(node, { factor, ms, at: performance.now() });
}

function parseParam(p: LiquidGlassParam): { key: SurfaceKey; active: boolean; onlens?: (on: boolean) => void } {
  return typeof p === 'string'
    ? { key: p, active: true }
    : { key: p.key, active: p.active !== false, onlens: p.onlens };
}

export const liquidGlass: Action<HTMLElement, LiquidGlassParam> = (node, param) => {
  let { key, active, onlens } = parseParam(param);
  let mode: GlassMode = 'off';
  let seen = false;
  let lens: Lens | null = null;
  let ro: ResizeObserver | null = null;
  let size: { w: number; h: number } | null = null;
  let raf = 0;
  let settle: ReturnType<typeof setTimeout> | undefined;
  let resizeTimer: ReturnType<typeof setTimeout> | undefined;
  let lastResize = 0;
  let attached = false;
  let attaching = false;
  let materializeNext = false;
  let unChange: (() => void) | null = null;
  let destroyed = false;

  const spec = (): LensSpec => SURFACES[key];

  function request(w: number, h: number): MapRequest {
    const s = spec();
    const radius = parseFloat(getComputedStyle(node).borderTopLeftRadius) || 0;
    const r = Math.min(radius, h / 2, w / 2);
    const b = Math.min(s.bezel, h / 2, r);
    const ms: Omit<FieldSpec, 'lut'> = { w, h, r, b, shift: s.shift, zoom: s.zoom, mask: s.mask };
    const k = mapScale(w, h, s.zoom);
    return { key: mapKey(ms, k), spec: ms, k };
  }

  function commitMap() {
    settle = undefined;
    if (!size || mode !== 'refract' || size.w < 2 || size.h < 2) return;
    const req = request(size.w, size.h);
    if (lens) glassRegistry.setMap(lens.id, req);
    // an inactive pill keeps its next map warm, so the next move is instant
    // (only with full motion: otherwise the thumb never turns into a lens)
    else if (!active && get(glassLive)) glassRegistry.prewarm(req);
  }

  function resizeNow() {
    clearTimeout(resizeTimer);
    resizeTimer = undefined;
    if (!lens || !size) return;
    lastResize = performance.now();
    glassRegistry.resizeLens(lens.id, size.w, size.h);
  }

  function resize() {
    // the moving thumb animates its width: rebuilding its filter every frame
    // is wasted work, so a transient lens follows at most every 100ms
    if (lens && attached && spec().mask === 'full') {
      const wait = lastResize + TRANSIENT_RESIZE_MS - performance.now();
      if (wait > 0) {
        resizeTimer ??= setTimeout(resizeNow, wait);
        return;
      }
    }
    resizeNow();
  }

  function flush() {
    raf = 0;
    if (!size || mode !== 'refract') return;
    if (lens) resize();
    clearTimeout(settle);
    // the first map is made at once; later ones wait for the size to settle
    if (lens && !lens.mapKey) commitMap();
    else settle = setTimeout(commitMap, SETTLE_MS);
  }

  function observe() {
    if (ro || typeof ResizeObserver !== 'function') return;
    ro = new ResizeObserver((entries) => {
      const e = entries[entries.length - 1];
      const bb = e.borderBoxSize?.[0];
      const w = Math.round(bb ? bb.inlineSize : node.offsetWidth);
      const h = Math.round(bb ? bb.blockSize : node.offsetHeight);
      if (size && size.w === w && size.h === h) return;
      size = { w, h };
      if (!raf) raf = requestAnimationFrame(flush);
    });
    ro.observe(node, { box: 'border-box' });
  }

  function attach(tries = 0) {
    if (!lens || attached || !lens.url) return;
    if (attaching && tries === 0) return;
    attaching = true;
    const id = lens.id;
    void tick().then(() =>
      requestAnimationFrame(() => {
        if (destroyed || !lens || lens.id !== id || mode !== 'refract' || !active) {
          attaching = false;
          return;
        }
        // a missing filter must never be referenced: Chromium drops the
        // whole backdrop-filter chain and the glass turns clear
        if (!document.getElementById(id)) {
          if (tries < 10) attach(tries + 1);
          else attaching = false;
          return;
        }
        attaching = false;
        attached = true;
        attachedIds.set(node, id);
        const live = get(glassLive);
        if (live && (materializeNext || spec().materialize)) animateScale(id, easeOut, MATERIALIZE_MS);
        materializeNext = false;
        node.style.setProperty('--lg-filter', `url(#${id})`);
        onlens?.(true);
        const p = pendingPulse.get(node);
        pendingPulse.delete(node);
        if (live && p && performance.now() - p.at < 400) pulse(id, p.factor, p.ms);
      }),
    );
  }

  function ensureLens() {
    if (destroyed || lens || !active || mode !== 'refract') return;
    lens = glassRegistry.addLens(spec());
    if (!lens) return; // over MAX_LENSES: this element stays on the CSS tier
    if (size) {
      glassRegistry.resizeLens(lens.id, size.w, size.h);
      commitMap();
    }
    attach();
  }

  function dropLens() {
    if (!lens) return;
    const was = attached;
    stopTween(lens.id);
    clearTimeout(resizeTimer);
    resizeTimer = undefined;
    // removeLens tells waiting elements a slot is free; our own listener
    // still sees `lens` set here, so it cannot re-add one
    glassRegistry.removeLens(lens.id);
    lens = null;
    attached = false;
    attaching = false;
    attachedIds.delete(node);
    node.style.removeProperty('--lg-filter');
    if (was) onlens?.(false);
  }

  function teardown() {
    ro?.disconnect();
    ro = null;
    cancelAnimationFrame(raf);
    raf = 0;
    clearTimeout(settle);
    settle = undefined;
    size = null;
    dropLens();
    pendingPulse.delete(node);
    node.style.removeProperty('--lg-filter');
    lightDriver.unregister(node);
    unChange?.();
    unChange = null;
  }

  function setup() {
    observe();
    // also retries an element refused at MAX_LENSES once a slot frees up
    unChange ??= glassRegistry.onChange(() => {
      ensureLens();
      attach();
    });
    if (spec().light) lightDriver.register(node);
    ensureLens();
  }

  const unMode = glassMode.subscribe((m) => {
    const was = mode;
    mode = m;
    if (m === 'refract') {
      // toggling the option on materializes every lens once
      if (seen && was !== 'refract') materializeNext = true;
      setup();
    } else if (was === 'refract' || !seen) {
      teardown();
    }
    seen = true;
  });

  function update(p: LiquidGlassParam) {
    const next = parseParam(p);
    onlens = next.onlens;
    if (next.key !== key) {
      teardown();
      key = next.key;
      active = next.active;
      if (mode === 'refract') setup();
      return;
    }
    if (next.active === active) return;
    active = next.active;
    if (mode !== 'refract') return;
    if (active) ensureLens();
    else {
      dropLens();
      commitMap();
    }
  }

  return {
    // untracked: update runs inside Svelte's render effect, and dropLens /
    // ensureLens read and write the registry's $state (and wake other lenses)
    update: (p: LiquidGlassParam) => untrack(() => update(p)),
    destroy() {
      destroyed = true;
      unMode();
      teardown();
    },
  };
};
