// Liquid glass specular light: the rim's bright side follows the pointer.
// Only lens surfaces (topbar, Settings header, Modal) register; cards keep
// the static 315deg (top-left) light.

export const REST_ANGLE = 315;

/** Degrees from the element centre to the pointer: 0 = up, clockwise,
 *  quantised to `step` (fewer style writes). */
export function lightAngle(px: number, py: number, cx: number, cy: number, step = 6): number {
  const deg = (Math.atan2(px - cx, -(py - cy)) * 180) / Math.PI;
  const q = Math.round(deg / step) * step;
  return ((q % 360) + 360) % 360;
}

/** `next` shifted by whole turns to be nearest `prev`, so the conic
 *  transition takes the short way round. */
export function unwrap(prev: number, next: number): number {
  return next + 360 * Math.round((prev - next) / 360);
}

type Entry = { rect: DOMRect | null; angle: number; raw: number };

export class LightDriver {
  #nodes = new Map<HTMLElement, Entry>();
  #running = false;
  #raf = 0;
  #pointer: { x: number; y: number } | null = null;

  register(node: HTMLElement): void {
    if (this.#nodes.has(node)) return;
    this.#nodes.set(node, { rect: null, angle: REST_ANGLE, raw: REST_ANGLE });
    if (this.#running) {
      this.#measure(node);
      this.#schedule();
    }
  }

  unregister(node: HTMLElement): void {
    if (!this.#nodes.delete(node)) return;
    node.style.removeProperty('--lg-light');
  }

  get size(): number {
    return this.#nodes.size;
  }

  start(): () => void {
    if (this.#running) return () => this.stop();
    this.#running = true;
    this.#remeasure();
    window.addEventListener('pointermove', this.#onMove, { passive: true });
    window.addEventListener('resize', this.#remeasure, { passive: true });
    window.addEventListener('scroll', this.#remeasure, { passive: true, capture: true });
    document.documentElement.addEventListener('pointerleave', this.#onLeave);
    return () => this.stop();
  }

  stop(): void {
    if (!this.#running) return;
    this.#running = false;
    cancelAnimationFrame(this.#raf);
    this.#raf = 0;
    window.removeEventListener('pointermove', this.#onMove);
    window.removeEventListener('resize', this.#remeasure);
    window.removeEventListener('scroll', this.#remeasure, { capture: true });
    document.documentElement.removeEventListener('pointerleave', this.#onLeave);
    this.#pointer = null;
    for (const [node, e] of this.#nodes) {
      e.angle = e.raw = REST_ANGLE;
      node.style.removeProperty('--lg-light');
    }
  }

  #measure(node: HTMLElement) {
    const e = this.#nodes.get(node);
    if (e) e.rect = node.getBoundingClientRect();
  }

  /** Resize/scroll: drop the cached rects; #apply re-measures lazily in the
   *  next frame, and only while a pointer is over the window. */
  #remeasure = () => {
    for (const e of this.#nodes.values()) e.rect = null;
    if (this.#pointer) this.#schedule();
  };

  #onMove = (ev: PointerEvent) => {
    this.#pointer = { x: ev.clientX, y: ev.clientY };
    this.#schedule();
  };

  #onLeave = () => {
    this.#pointer = null;
    this.#schedule();
  };

  #schedule() {
    if (this.#raf || !this.#running) return;
    this.#raf = requestAnimationFrame(this.#apply);
  }

  #apply = () => {
    this.#raf = 0;
    const p = this.#pointer;
    for (const [node, e] of this.#nodes) {
      if (!e.rect) this.#measure(node);
      const r = e.rect!;
      const next = p ? lightAngle(p.x, p.y, r.left + r.width / 2, r.top + r.height / 2) : REST_ANGLE;
      if (next === e.raw) continue;
      e.raw = next;
      e.angle = unwrap(e.angle, next);
      // on the lens node, never :root, so a step restyles only that subtree
      node.style.setProperty('--lg-light', `${e.angle}deg`);
    }
  };
}

export const lightDriver = new LightDriver();
