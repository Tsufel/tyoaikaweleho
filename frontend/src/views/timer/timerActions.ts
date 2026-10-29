import { get, readable, writable } from 'svelte/store';
import { api, runFlow } from '../../lib/api';
import type { ConfirmList, HHMM, StartMode, StopResult, StopSource, TimerResult } from '../../lib/api/types';
import { alert, reportError } from '../../lib/stores/confirm';
import { showEntry } from '../../lib/stores/entries';
import { offerRecovery } from '../../lib/stores/recovery';
import { refreshTimer, setTimer, timer } from '../../lib/stores/timer';
import { toast } from '../../lib/stores/toasts';
import { formatDuration, hhmm } from '../../lib/time';

// Module-level so F5 keeps working while TimerView is unmounted (stats route).

/** Job picked in the idle combobox; follows the default job while idle. */
export const jobDraft = writable('');
/** A start/stop call is in flight. */
export const busy = writable(false);
/** Bumped after every saved shift (fire burst / ring flourish). */
export const burst = writable(0);
/** Wall-clock ms, ticking on each second boundary (idle start dial). */
export const wallClock = readable(Date.now(), (set) => {
  let t: ReturnType<typeof setTimeout>;
  const tick = () => {
    set(Date.now());
    t = setTimeout(tick, 1000 - (Date.now() % 1000) + 5);
  };
  tick();
  return () => clearTimeout(t);
});

let lastDefault: string | null = null;
timer.subscribe((t) => {
  if (t.default_job_shift === lastDefault) return;
  lastDefault = t.default_job_shift;
  if (!t.running) jobDraft.set(t.default_job_shift);
});

async function guarded<T>(fn: () => Promise<T>): Promise<T | undefined> {
  if (get(busy)) return undefined;
  busy.set(true);
  try {
    return await fn();
  } finally {
    busy.set(false);
  }
}

/** §6.2 — START NOW / ⏰ default / picked time. */
export function startShift(
  mode: StartMode,
  time?: HHMM | null,
  job?: string | null,
  preset?: ConfirmList,
): Promise<TimerResult | undefined> {
  return guarded(async () => {
    const jobShift = (job ?? get(jobDraft)).trim() || null;
    const r = await runFlow((c) => api.timer_start(mode, mode === 'at' ? time ?? null : null, jobShift, c), preset);
    if (r.timer) setTimer(r.timer);
    if (r.status === 'invalid') {
      await alert('Invalid start time', r.message, 'error');
    } else if (r.status === 'error') {
      if (r.error.code === 'recovery_pending') await offerRecovery();
      else if (r.error.code === 'already_running') {
        if (!r.timer) await refreshTimer();
      } else {
        if (!r.timer) await refreshTimer();
        await reportError(r, 'Could not start the shift');
      }
    }
    return r;
  });
}

/** §6.1 — STOP button ('button') or F5 ('shortcut'). A failed save leaves the
 *  shift running (Python restarts it); the timer payload says so. */
export function stopShift(source: Exclude<StopSource, 'close'>): Promise<StopResult | undefined> {
  return guarded(async () => {
    const r = await runFlow((c) => api.timer_stop(source, c));
    if (r.timer) setTimer(r.timer);
    else await refreshTimer();
    if (r.status === 'saved') {
      burst.update((n) => n + 1);
      if (r.entry) {
        const mins = r.entry.minutes;
        toast(`Shift saved${mins != null ? ` — ${formatDuration(mins)}` : ''}`, { tone: 'success', ms: 4000 });
        await showEntry(r.entry);
      }
    } else if (r.status === 'discarded') {
      toast(r.message ?? 'Shift discarded', { tone: 'warning', ms: 5000 });
    } else if (r.status === 'error') {
      if (r.error.code === 'stale' || r.error.code === 'not_running') {
        await refreshTimer();
        toast(r.error.message || 'The shift changed in the meantime.', { tone: 'warning', ms: 5000 });
      } else {
        await reportError(r, 'Could not save shift');
      }
    }
    return r;
  });
}

/** Start dial: `at` is an exact past start (epoch ms) or null for now. Only
 *  HH:MM goes to Python, which asks "now or yesterday?" when that HH:MM is
 *  just ahead of the clock — the dial already knows it meant the past one. */
export function startDialShift(at: number | null): Promise<TimerResult | undefined> {
  if (at == null) return startShift('now');
  return startShift('at', hhmm(new Date(at)), null, [{ kind: 'start_ahead', choice: 'earlier' }]);
}

/** F5: stop (with confirm) when running, else start now with the picked job. */
export function toggleTimer(): Promise<unknown> {
  return get(timer).running ? stopShift('shortcut') : startShift('now');
}
