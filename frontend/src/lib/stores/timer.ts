import { derived, get, readable, writable, type Readable } from 'svelte/store';
import { api } from '../api/bridge';
import { onEvent } from '../api/events';
import type { TimerState } from '../api/types';
import { pageVisible } from './app';

export const IDLE_TIMER: TimerState = {
  running: false,
  start_iso: null,
  start_epoch_ms: null,
  job_shift: '',
  default_job_shift: '',
  default_start_time: '09:30',
  pay_rate: 20,
  recovery_pending: false,
};

const state = writable<TimerState>(IDLE_TIMER);

/** Python's timer state. The JS clock only ticks from start_epoch_ms;
 *  Python is authoritative on stop. */
export const timer: Readable<TimerState> = { subscribe: state.subscribe };

export function setTimer(t: TimerState | undefined | null): void {
  if (t) state.set(t);
}

export async function refreshTimer(): Promise<void> {
  const r = await api.get_timer();
  if (r.ok) setTimer(r.timer);
}

function elapsedFor(t: TimerState): number {
  if (!t.running || t.start_epoch_ms == null) return 0;
  return Math.max(0, Math.floor((Date.now() - t.start_epoch_ms) / 1000));
}

/** Whole seconds since start; ticks 1 Hz on the second boundary while running
 *  and visible (paused when hidden, recomputed on return). */
export const elapsedSeconds: Readable<number> = readable(0, (set) => {
  let handle: ReturnType<typeof setTimeout> | null = null;
  let t = get(state);
  let visible = true;
  const stop = () => {
    if (handle !== null) clearTimeout(handle);
    handle = null;
  };
  const tick = () => {
    stop();
    set(elapsedFor(t));
    if (!t.running || !visible || t.start_epoch_ms == null) return;
    const ms = 1000 - ((Date.now() - t.start_epoch_ms) % 1000);
    handle = setTimeout(tick, ms + 5);
  };
  const u1 = state.subscribe((v) => {
    t = v;
    tick();
  });
  const u2 = pageVisible.subscribe((v) => {
    visible = v;
    tick();
  });
  return () => {
    stop();
    u1();
    u2();
  };
});

/** Live earnings of the running shift (€). */
export const liveEarnings: Readable<number> = derived([state, elapsedSeconds], ([$t, $s]) =>
  $t.running ? ($s / 3600) * $t.pay_rate : 0,
);

onEvent('timer:changed', (t) => setTimer(t));
