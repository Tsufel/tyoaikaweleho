import { get, readable, writable } from 'svelte/store';
import { emitFx } from '../../fx/fire/fxBus';
import { api, runFlow } from '../../lib/api';
import type { ConfirmList, EntryRow, HHMM, StartMode, StopResult, StopSource, TimerResult } from '../../lib/api/types';
import { alert, reportError } from '../../lib/stores/confirm';
import { showEntry } from '../../lib/stores/entries';
import { lulz } from '../../lib/stores/motion';
import { offerRecovery } from '../../lib/stores/recovery';
import { refreshTimer, setTimer, timer } from '../../lib/stores/timer';
import { toast } from '../../lib/stores/toasts';
import { hhmm } from '../../lib/time';
import { savedToastText } from './timerLogic';

// Module-level so F5 keeps working while TimerView is unmounted (stats route).

/** Job picked in the idle combobox; follows the default job while idle. */
export const jobDraft = writable('');
/** A start/stop call is in flight. */
export const busy = writable(false);
/** Bumped after every saved shift (fire burst / ring flourish). */
export const burst = writable(0);
/** start_iso of the shift whose "Still working?" banner was dismissed. */
export const stillWorkingDismissed = writable<string | null>(null);
/** The entry the last saved shift wrote, set just before burst is bumped. */
export const savedEntry = writable<EntryRow | null>(null);
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
    if (r.status === 'ok' && r.timer.running) emitFx({ kind: 'ignite' });
    if (r.status === 'invalid') {
      await alert(r.field === 'job_shift' ? 'Invalid shift name' : 'Invalid start time', r.message, 'error');
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
  return guarded(async () => afterStop(await runFlow((c) => api.timer_stop(source, c))));
}

/** STOP ▾: save the running shift as ending at a past HH:MM (§6.3a). */
export function stopShiftAt(end: HHMM): Promise<StopResult | undefined> {
  return guarded(async () => {
    const r = await runFlow((c) => api.timer_stop_at(end, c));
    if (r.status === 'invalid') {
      if (r.timer) setTimer(r.timer);
      await alert('Invalid end time', r.message, 'error');
      return r;
    }
    return afterStop(r);
  });
}

/** Shared tail of STOP and STOP at: fx, toast, show the saved entry. */
async function afterStop(r: StopResult): Promise<StopResult> {
  if (r.timer) setTimer(r.timer);
  else await refreshTimer();
  if (r.status === 'saved') {
    savedEntry.set(r.entry ?? null);
    burst.update((n) => n + 1);
    emitFx({ kind: 'blast', minutes: r.entry?.minutes ?? null });
    if (r.entry) {
      const mins = r.entry.minutes;
      if (r.overlap_warning) toast(`${savedToastText(mins, 0)}. ${r.overlap_warning}`, { tone: 'warning', ms: 12000 });
      else toast(savedToastText(mins, r.timer?.pay_rate ?? 0, get(lulz)), { tone: 'success', ms: 4000 });
      await showEntry(r.entry);
    }
  } else if (r.status === 'discarded') {
    emitFx({ kind: 'fizzle' });
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
}

/** Fix the running shift's start (HH:MM) and/or job (§6.3a). */
export function adjustShift(time: HHMM | null, job: string | null): Promise<TimerResult | undefined> {
  return guarded(async () => {
    const startIso = get(timer).start_iso;
    if (!startIso) return undefined;
    const r = await runFlow((c) => api.timer_adjust(startIso, time, job, c));
    if (r.timer) setTimer(r.timer);
    if (r.status === 'invalid') {
      await alert('Invalid start time', r.message, 'error');
    } else if (r.status === 'error') {
      if (r.error.code === 'stale' || r.error.code === 'not_running') {
        await refreshTimer();
        toast(r.error.message || 'The shift changed in the meantime.', { tone: 'warning', ms: 5000 });
      } else {
        await reportError(r, 'Could not change the shift');
      }
    }
    return r;
  });
}

/** Start dial: `at` is an exact past start (epoch ms) or null for now. Only
 *  HH:MM goes to Python, which asks "now or yesterday?" when that HH:MM is
 *  just ahead of the clock, and "that far back?" when it's hours ago — the
 *  dial already knows it meant the past one. */
export function startDialShift(at: number | null): Promise<TimerResult | undefined> {
  if (at == null) return startShift('now');
  return startShift('at', hhmm(new Date(at)), null, [
    { kind: 'start_ahead', choice: 'earlier' },
    { kind: 'start_backdate', choice: 'earlier' },
  ]);
}

/** F5: stop (with confirm) when running, else start now with the picked job. */
export function toggleTimer(): Promise<unknown> {
  return get(timer).running ? stopShift('shortcut') : startShift('now');
}
