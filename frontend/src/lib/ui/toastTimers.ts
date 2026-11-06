/** Toast countdowns. Each toast counts down its own `ms`; every countdown
 *  pauses while any hold is on (pointer over the stack, focus inside it, the
 *  window hidden or in the background), so an Undo can't run out unseen. */

export type ToastHold = 'hover' | 'focus' | 'away';

interface TimedToast {
  id: number;
  ms: number;
  count?: number;
}

interface Clock {
  left: number;
  started: number;
  count: number;
  handle?: ReturnType<typeof setTimeout>;
}

/** Time a paused toast gets back at least, so it can still be read. */
export const RESUME_MIN_MS = 3000;

export function createToastTimers(onExpire: (id: number) => void, now: () => number = Date.now) {
  const clocks = new Map<number, Clock>();
  const holds = new Set<ToastHold>();
  let current: TimedToast[] = [];

  function arm(t: TimedToast) {
    if (t.ms <= 0) return;
    const count = t.count ?? 1;
    let c = clocks.get(t.id);
    if (c && c.count !== count) {
      // a duplicate came in: start the full time again
      clearTimeout(c.handle);
      c = undefined;
    }
    if (!c) {
      c = { left: t.ms, started: 0, count };
      clocks.set(t.id, c);
    }
    if (holds.size || c.handle) return;
    c.started = now();
    c.handle = setTimeout(() => {
      clocks.delete(t.id);
      onExpire(t.id);
    }, c.left);
  }

  function pause() {
    for (const c of clocks.values()) {
      if (!c.handle) continue;
      clearTimeout(c.handle);
      c.handle = undefined;
      c.left = Math.max(RESUME_MIN_MS, c.left - (now() - c.started));
    }
  }

  return {
    /** The toast list changed. */
    sync(list: TimedToast[]) {
      current = list;
      const ids = new Set(list.map((t) => t.id));
      for (const [id, c] of clocks) {
        if (!ids.has(id)) {
          clearTimeout(c.handle);
          clocks.delete(id);
        }
      }
      for (const t of list) arm(t);
    },
    /** Turn one pause source on or off. */
    hold(source: ToastHold, on: boolean) {
      const was = holds.size > 0;
      if (on) holds.add(source);
      else holds.delete(source);
      if (!was && holds.size) pause();
      else if (was && !holds.size) for (const t of current) arm(t);
    },
    get paused() {
      return holds.size > 0;
    },
    destroy() {
      for (const c of clocks.values()) clearTimeout(c.handle);
      clocks.clear();
    },
  };
}
