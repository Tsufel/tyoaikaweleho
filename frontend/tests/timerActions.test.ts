import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ConfirmRequest, TimerState } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({
  timer_start: vi.fn(),
  timer_stop: vi.fn(),
  close_app: vi.fn(),
  get_timer: vi.fn(),
  bootstrap: vi.fn(),
  list_month: vi.fn(),
}));
const spies = vi.hoisted(() => ({ showEntry: vi.fn(), offerRecovery: vi.fn() }));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/lib/stores/entries', () => ({ showEntry: spies.showEntry }));
vi.mock('../src/lib/stores/recovery', async () => {
  const { writable } = await import('svelte/store');
  return { offerRecovery: spies.offerRecovery, pendingRecovery: writable(null) };
});

const { dialogs } = await import('../src/lib/stores/confirm');
const { setTimer, timer, IDLE_TIMER } = await import('../src/lib/stores/timer');
const { toasts, clearToasts } = await import('../src/lib/stores/toasts');
const actions = await import('../src/views/timer/timerActions');
const { handleCloseRequest } = await import('../src/views/modals/closeFlow');

// ── dialog driver: answers each confirm with the next scripted choice ──
let script: string[] = [];
let shown: { kind?: string; title: string }[] = [];
const seen = new Set<number>();
dialogs.subscribe((items) => {
  for (const d of items) {
    if (d.type !== 'choice' || seen.has(d.id)) continue;
    seen.add(d.id);
    shown.push({ kind: d.request.kind, title: d.request.title });
    const choice = script.shift() ?? d.request.cancel;
    queueMicrotask(() => d.resolve(choice));
  }
});

const START = '2026-10-29T09:00:00';
const running: TimerState = {
  ...IDLE_TIMER,
  running: true,
  start_iso: START,
  start_epoch_ms: Date.now() - 3600_000,
  job_shift: 'Support',
  default_job_shift: 'Support',
};
const idle: TimerState = { ...IDLE_TIMER, default_job_shift: 'Support' };

function needs(kind: ConfirmRequest['kind'], options: string[], def: string, cancel: string) {
  return {
    ok: false,
    status: 'needs_confirm',
    confirm: {
      kind,
      title: kind,
      message: kind,
      options: options.map((id) => ({ id, label: id })),
      default: def,
      cancel,
      icon: 'warning',
      token: START,
      details: { start_iso: START, elapsed_minutes: 60 },
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  script = [];
  shown = [];
  clearToasts();
  fakeApi.get_timer.mockResolvedValue({ ok: true, status: 'ok', timer: get(timer) });
});

describe('stop (§6.1)', () => {
  it('F5 asks stop_shift; "keep" leaves the shift running', async () => {
    setTimer(running);
    fakeApi.timer_stop
      .mockResolvedValueOnce(needs('stop_shift', ['stop', 'keep'], 'stop', 'keep'))
      .mockResolvedValueOnce({ ok: true, status: 'cancelled', timer: running });
    script = ['keep'];
    await actions.toggleTimer();
    expect(fakeApi.timer_stop).toHaveBeenNthCalledWith(1, 'shortcut', undefined);
    expect(fakeApi.timer_stop).toHaveBeenNthCalledWith(2, 'shortcut', [{ kind: 'stop_shift', choice: 'keep', token: START }]);
    expect(get(timer).running).toBe(true);
    expect(get(toasts)).toHaveLength(0);
  });

  it('Escape on stop_shift answers cancel (keep)', async () => {
    setTimer(running);
    fakeApi.timer_stop
      .mockResolvedValueOnce(needs('stop_shift', ['stop', 'keep'], 'stop', 'keep'))
      .mockResolvedValueOnce({ ok: true, status: 'cancelled', timer: running });
    await actions.stopShift('shortcut');
    expect(fakeApi.timer_stop.mock.calls[1][1]).toEqual([{ kind: 'stop_shift', choice: 'keep', token: START }]);
  });

  it('save failure keeps the timer running and reports it', async () => {
    setTimer(running);
    fakeApi.timer_stop.mockResolvedValueOnce({
      ok: false,
      status: 'error',
      error: { code: 'save_failed', message: 'The shift could not be saved and is still running.' },
      timer: running,
    });
    await actions.stopShift('button');
    expect(get(timer).running).toBe(true);
    expect(shown.at(-1)?.title).toBe('Could not save shift');
    expect(get(actions.burst)).toBe(0);
  });

  it('under a minute → toast with the Python message', async () => {
    setTimer(running);
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: true, status: 'discarded', timer: idle, message: 'Shift under a minute — not saved' });
    await actions.stopShift('button');
    expect(get(timer).running).toBe(false);
    expect(get(toasts).map((t) => t.message)).toEqual(['Shift under a minute — not saved']);
  });

  it('over_24h → discard → discard_shift cancel keeps running; answers accumulate', async () => {
    setTimer(running);
    fakeApi.timer_stop
      .mockResolvedValueOnce(needs('over_24h', ['save', 'discard', 'keep'], 'keep', 'keep'))
      .mockResolvedValueOnce(needs('discard_shift', ['discard', 'cancel'], 'cancel', 'cancel'))
      .mockResolvedValueOnce({ ok: true, status: 'cancelled', timer: running });
    script = ['discard', 'cancel'];
    await actions.stopShift('button');
    expect(fakeApi.timer_stop.mock.calls[2][1]).toEqual([
      { kind: 'over_24h', choice: 'discard', token: START },
      { kind: 'discard_shift', choice: 'cancel', token: START },
    ]);
    expect(get(timer).running).toBe(true);
  });

  it('saved → burst, toast and jump to the entry', async () => {
    setTimer(running);
    const entry = { id: 'e1', date: '2026-10-29', job_shift: 'Support', time_in: '09:00', time_out: '17:00', minutes: 480 };
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: true, status: 'saved', timer: idle, entry });
    await actions.stopShift('button');
    expect(get(actions.burst)).toBe(1);
    expect(spies.showEntry).toHaveBeenCalledWith(entry);
    expect(get(toasts)[0].message).toBe('Shift saved — 8h 00m');
  });

  it('stale → re-reads the timer', async () => {
    setTimer(running);
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: false, status: 'error', error: { code: 'stale', message: 'changed' }, timer: running });
    await actions.stopShift('button');
    expect(fakeApi.get_timer).toHaveBeenCalled();
  });
});

describe('start (§6.2)', () => {
  it('starts with the picked job', async () => {
    setTimer(idle);
    actions.jobDraft.set('Night');
    fakeApi.timer_start.mockResolvedValueOnce({ ok: true, status: 'ok', timer: { ...running, job_shift: 'Night' } });
    await actions.toggleTimer();
    expect(fakeApi.timer_start).toHaveBeenCalledWith('now', null, 'Night', undefined);
    expect(get(timer).running).toBe(true);
  });

  it('start_ahead "now" re-calls with the answer', async () => {
    setTimer(idle);
    fakeApi.timer_start
      .mockResolvedValueOnce({ ...needs('start_ahead', ['now', 'earlier', 'cancel'], 'now', 'cancel'), confirm: { ...needs('start_ahead', ['now', 'earlier', 'cancel'], 'now', 'cancel').confirm, token: undefined } })
      .mockResolvedValueOnce({ ok: true, status: 'ok', timer: running });
    script = ['now'];
    await actions.startShift('at', '23:30');
    expect(fakeApi.timer_start.mock.calls[0].slice(0, 2)).toEqual(['at', '23:30']);
    expect(fakeApi.timer_start.mock.calls[1][3]).toEqual([{ kind: 'start_ahead', choice: 'now' }]);
  });

  it('start dial pre-answers start_ahead with the past (yesterday) start', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({ ok: true, status: 'ok', timer: running });
    await actions.startDialShift(new Date(2026, 9, 29, 1, 30).getTime());
    expect(fakeApi.timer_start).toHaveBeenCalledTimes(1);
    expect(fakeApi.timer_start.mock.calls[0].slice(0, 2)).toEqual(['at', '01:30']);
    expect(fakeApi.timer_start.mock.calls[0][3]).toEqual([{ kind: 'start_ahead', choice: 'earlier' }]);
    expect(shown).toHaveLength(0);
  });

  it('start dial at "now" is a plain start now', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({ ok: true, status: 'ok', timer: running });
    await actions.startDialShift(null);
    expect(fakeApi.timer_start.mock.calls[0][0]).toBe('now');
    expect(fakeApi.timer_start.mock.calls[0][3]).toBeUndefined();
  });

  it('recovery pending re-offers recovery instead of starting', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({
      ok: false,
      status: 'error',
      error: { code: 'recovery_pending', message: 'Resolve the unfinished shift first.' },
      timer: idle,
    });
    await actions.startShift('now');
    expect(spies.offerRecovery).toHaveBeenCalled();
    expect(shown).toHaveLength(0);
  });

  it('jobDraft follows the default job only while idle', () => {
    setTimer({ ...idle, default_job_shift: 'A' });
    expect(get(actions.jobDraft)).toBe('A');
    setTimer({ ...running, default_job_shift: 'B' });
    expect(get(actions.jobDraft)).toBe('A');
  });

  it('ignores a second click while a call is in flight', async () => {
    setTimer(idle);
    let release!: (v: unknown) => void;
    fakeApi.timer_start.mockReturnValueOnce(new Promise((r) => (release = r)));
    const first = actions.startShift('now');
    expect(await actions.startShift('now')).toBeUndefined();
    release({ ok: true, status: 'ok', timer: running });
    await first;
    expect(fakeApi.timer_start).toHaveBeenCalledTimes(1);
  });
});

describe('close (§6.8)', () => {
  it('Stay open → nothing changes', async () => {
    setTimer(running);
    fakeApi.close_app
      .mockResolvedValueOnce(needs('close_running', ['stop_close', 'close', 'cancel'], 'stop_close', 'cancel'))
      .mockResolvedValueOnce({ ok: true, status: 'cancelled', timer: running });
    await handleCloseRequest();
    expect(shown[0].kind).toBe('close_running');
    expect(fakeApi.close_app.mock.calls[1][0]).toEqual([{ kind: 'close_running', choice: 'cancel', token: START }]);
    expect(get(timer).running).toBe(true);
  });

  it('stop & close with a failed save stays open, timer running, error shown', async () => {
    setTimer(running);
    fakeApi.close_app
      .mockResolvedValueOnce(needs('close_running', ['stop_close', 'close', 'cancel'], 'stop_close', 'cancel'))
      .mockResolvedValueOnce({ ok: false, status: 'error', error: { code: 'save_failed', message: 'locked' }, timer: running });
    script = ['stop_close'];
    await handleCloseRequest();
    expect(get(timer).running).toBe(true);
    expect(shown.at(-1)?.title).toBe('Could not save shift');
  });
});
