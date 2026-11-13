import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FxEvent } from '../src/fx/fire/fxBus';
import type { ConfirmRequest, TimerState } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({
  timer_start: vi.fn(),
  timer_stop: vi.fn(),
  timer_stop_at: vi.fn(),
  timer_adjust: vi.fn(),
  close_app: vi.fn(),
  get_timer: vi.fn(),
  bootstrap: vi.fn(),
  list_month: vi.fn(),
  revert_entry: vi.fn(),
}));
const spies = vi.hoisted(() => ({ showEntry: vi.fn(), refreshMonth: vi.fn(), offerRecovery: vi.fn() }));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/lib/stores/entries', () => ({ showEntry: spies.showEntry, refreshMonth: spies.refreshMonth }));
vi.mock('../src/lib/stores/recovery', async () => {
  const { writable } = await import('svelte/store');
  return { offerRecovery: spies.offerRecovery, pendingRecovery: writable(null) };
});

const { dialogs } = await import('../src/lib/stores/confirm');
const { setTimer, timer, IDLE_TIMER } = await import('../src/lib/stores/timer');
const { toasts, clearToasts } = await import('../src/lib/stores/toasts');
const actions = await import('../src/views/timer/timerActions');
const { handleCloseRequest } = await import('../src/views/modals/closeFlow');
const { onFx } = await import('../src/fx/fire/fxBus');

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

// ── fx bus spy ──
let fx: FxEvent[] = [];
let unsubFx = () => {};

beforeEach(() => {
  vi.clearAllMocks();
  script = [];
  shown = [];
  clearToasts();
  fakeApi.get_timer.mockResolvedValue({ ok: true, status: 'ok', timer: get(timer) });
  fx = [];
  unsubFx = onFx((e) => fx.push(e));
});
afterEach(() => unsubFx());

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
    expect(fx).toEqual([]);
  });

  it('Escape on stop_shift answers cancel (keep)', async () => {
    setTimer(running);
    fakeApi.timer_stop
      .mockResolvedValueOnce(needs('stop_shift', ['stop', 'keep'], 'stop', 'keep'))
      .mockResolvedValueOnce({ ok: true, status: 'cancelled', timer: running });
    await actions.stopShift('shortcut');
    expect(fakeApi.timer_stop.mock.calls[1][1]).toEqual([{ kind: 'stop_shift', choice: 'keep', token: START }]);
    expect(fx).toEqual([]);
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
    expect(fx).toEqual([]);
  });

  it('under a minute → toast with the Python message', async () => {
    setTimer(running);
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: true, status: 'discarded', timer: idle, message: 'Shift under a minute — not saved' });
    await actions.stopShift('button');
    expect(get(timer).running).toBe(false);
    expect(get(toasts).map((t) => t.message)).toEqual(['Shift under a minute — not saved']);
    expect(fx).toEqual([{ kind: 'fizzle' }]);
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
    expect(fx).toEqual([]);
  });

  it('saved → burst, toast and jump to the entry', async () => {
    setTimer(running);
    const entry = { id: 'e1', date: '2026-10-29', job_shift: 'Support', time_in: '09:00', time_out: '17:00', minutes: 480 };
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: true, status: 'saved', timer: idle, entry });
    // At emit time: burst already bumped, toast not yet shown.
    let atBlast: { burst: number; toasts: number } | null = null;
    const unsub = onFx((e) => {
      if (e.kind === 'blast') atBlast = { burst: get(actions.burst), toasts: get(toasts).length };
    });
    let fxAtShow: FxEvent[] = [];
    spies.showEntry.mockImplementationOnce(() => void (fxAtShow = [...fx]));
    const burst0 = get(actions.burst);
    await actions.stopShift('button');
    unsub();
    expect(get(actions.burst)).toBe(burst0 + 1);
    expect(spies.showEntry).toHaveBeenCalledWith(entry);
    expect(get(toasts)[0].message).toBe(`Shift saved — 8h 00m · €${(8 * idle.pay_rate).toFixed(2)} earned`);
    expect(fx).toEqual([{ kind: 'blast', minutes: 480 }]);
    expect(fxAtShow).toEqual(fx);
    expect(atBlast).toEqual({ burst: burst0 + 1, toasts: 0 });
  });

  it('saved with an overlap → warning toast that stays longer', async () => {
    setTimer(running);
    const entry = { id: 'e1', date: '2026-10-29', job_shift: 'Support', time_in: '09:00', time_out: '17:00', minutes: 480 };
    fakeApi.timer_stop.mockResolvedValueOnce({
      ok: true,
      status: 'saved',
      timer: idle,
      entry,
      overlap_warning: 'This shift overlaps another entry:\n• Sales on Thu 29 Oct, 08:00–10:00',
    });
    await actions.stopShift('button');
    const t = get(toasts).at(-1)!;
    expect(t.tone).toBe('warning');
    expect(t.ms).toBe(12000);
    expect(t.message).toBe('Shift saved — 8h 00m. This shift overlaps another entry:\n• Sales on Thu 29 Oct, 08:00–10:00');
    expect(spies.showEntry).toHaveBeenCalledWith(entry);
  });

  it('saved rounded → says from what, offers Keep exact for 10 s', async () => {
    setTimer(running);
    const entry = { id: 'e1', date: '2026-10-29', job_shift: 'Support', time_in: '09:00', time_out: '17:00', minutes: 480 };
    const before = { ...entry, time_in: '09:07', time_out: '16:41', minutes: 454 };
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: true, status: 'saved', timer: idle, entry, rounded: { before, token: 'tok' } });
    await actions.stopShift('button');
    const t = get(toasts).at(-1)!;
    expect(t.message).toBe(`Shift saved — 8h 00m · €${(8 * idle.pay_rate).toFixed(2)} earned. Rounded from 09:07–16:41`);
    expect([t.tone, t.ms, t.label, t.undo]).toEqual(['success', 10000, 'Keep exact', true]);

    spies.showEntry.mockClear();
    fakeApi.revert_entry.mockResolvedValueOnce({ ok: true, status: 'saved', entry: before });
    await t.action!();
    expect(fakeApi.revert_entry).toHaveBeenCalledWith(before, 'tok');
    expect(spies.showEntry).toHaveBeenCalledWith(before);
    expect(get(toasts).at(-1)!.message).toBe('Kept the exact times 09:07–16:41.');
  });

  it('saved rounded with an overlap → one warning toast with both notes', async () => {
    setTimer(running);
    const entry = { id: 'e1', date: '2026-10-29', job_shift: 'Support', time_in: '09:00', time_out: '17:00', minutes: 480 };
    const before = { ...entry, time_in: '09:07', time_out: '16:41', minutes: 454 };
    fakeApi.timer_stop.mockResolvedValueOnce({
      ok: true, status: 'saved', timer: idle, entry, rounded: { before, token: 'tok' },
      overlap_warning: 'This shift overlaps another entry:\n• Sales on Thu 29 Oct, 08:00–10:00',
    });
    await actions.stopShift('button');
    const t = get(toasts).at(-1)!;
    expect(t.message).toBe('Shift saved — 8h 00m. Rounded from 09:07–16:41. This shift overlaps another entry:\n• Sales on Thu 29 Oct, 08:00–10:00');
    expect([t.tone, t.ms, t.label]).toEqual(['warning', 12000, 'Keep exact']);
  });

  it('Keep exact after the shift changed or went → says so, changes nothing', async () => {
    const { keepExact } = await import('../src/lib/stores/keepExact');
    const before = { id: 'e1', date: '2026-10-29', job_shift: 'Support', time_in: '09:07', time_out: '16:41', minutes: 454 };
    spies.showEntry.mockClear();
    fakeApi.revert_entry.mockResolvedValueOnce({ ok: false, status: 'error', error: { code: 'stale', message: '' } });
    await keepExact({ before, token: 'tok' });
    expect(get(toasts).at(-1)!.message).toBe('That shift was changed again since, so its times were left as they are.');
    fakeApi.revert_entry.mockResolvedValueOnce({ ok: false, status: 'error', error: { code: 'not_found', message: '' } });
    await keepExact({ before, token: 'tok' });
    expect(spies.refreshMonth).toHaveBeenCalledWith({ commit: false });
    expect(get(toasts).at(-1)!.message).toBe('That shift no longer exists.');
    expect(spies.showEntry).not.toHaveBeenCalled();
  });

  it('not_running → re-reads the timer, no fx', async () => {
    setTimer(running);
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: false, status: 'error', error: { code: 'not_running', message: '' } });
    fakeApi.get_timer.mockResolvedValueOnce({ ok: true, status: 'ok', timer: idle });
    await actions.stopShift('button');
    expect(get(timer).running).toBe(false);
    expect(fx).toEqual([]);
  });

  it('saved without an entry → blast with null minutes', async () => {
    setTimer(running);
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: true, status: 'saved', timer: idle });
    await actions.stopShift('button');
    expect(fx).toEqual([{ kind: 'blast', minutes: null }]);
  });

  it('stale → re-reads the timer', async () => {
    setTimer(running);
    fakeApi.timer_stop.mockResolvedValueOnce({ ok: false, status: 'error', error: { code: 'stale', message: 'changed' }, timer: running });
    await actions.stopShift('button');
    expect(fakeApi.get_timer).toHaveBeenCalled();
    expect(fx).toEqual([]);
  });
});

describe('stop at / adjust (§6.3a)', () => {
  const entry = { id: 'e2', date: '2026-10-29', job_shift: 'Support', time_in: '09:00', time_out: '17:00', minutes: 480 };

  it('stop at saves like STOP, with the pay in the toast', async () => {
    setTimer(running);
    fakeApi.timer_stop_at.mockResolvedValueOnce({ ok: true, status: 'saved', timer: { ...idle, pay_rate: 20 }, entry });
    await actions.stopShiftAt('17:00');
    expect(fakeApi.timer_stop_at).toHaveBeenCalledWith('17:00', undefined);
    expect(get(toasts)[0].message).toBe('Shift saved — 8h 00m · €160.00 earned');
    expect(fx).toEqual([{ kind: 'blast', minutes: 480 }]);
    expect(spies.showEntry).toHaveBeenCalledWith(entry);
  });

  it('stop at a time still ahead → alert, keeps running, no fx', async () => {
    setTimer(running);
    fakeApi.timer_stop_at.mockResolvedValueOnce({ ok: false, status: 'invalid', field: 'end', message: 'ahead', timer: running });
    await actions.stopShiftAt('23:00');
    expect(shown.at(-1)?.title).toBe('Invalid end time');
    expect(get(timer).running).toBe(true);
    expect(fx).toEqual([]);
  });

  it('stop at a long shift asks long_entry with the token', async () => {
    setTimer(running);
    fakeApi.timer_stop_at
      .mockResolvedValueOnce(needs('long_entry', ['save', 'cancel'], 'save', 'cancel'))
      .mockResolvedValueOnce({ ok: true, status: 'cancelled', timer: running });
    script = ['cancel'];
    await actions.stopShiftAt('06:00');
    expect(fakeApi.timer_stop_at).toHaveBeenLastCalledWith('06:00', [{ kind: 'long_entry', choice: 'cancel', token: START }]);
    expect(fx).toEqual([]);
  });

  it('adjust sends the shown start and applies the new timer', async () => {
    setTimer(running);
    const moved = { ...running, start_iso: '2026-10-29T08:30:00', job_shift: 'Sales' };
    fakeApi.timer_adjust.mockResolvedValueOnce({ ok: true, status: 'ok', timer: moved });
    await actions.adjustShift('08:30', 'Sales');
    expect(fakeApi.timer_adjust).toHaveBeenCalledWith(START, '08:30', 'Sales', undefined);
    expect(get(timer)).toEqual(moved);
  });

  it('adjust that went stale re-reads the timer', async () => {
    setTimer(running);
    fakeApi.timer_adjust.mockResolvedValueOnce({ ok: false, status: 'error', error: { code: 'stale', message: 'changed' } });
    await actions.adjustShift('08:30', null);
    expect(fakeApi.get_timer).toHaveBeenCalled();
    expect(get(toasts).at(-1)?.message).toBe('changed');
  });

  it('adjust does nothing while idle', async () => {
    setTimer(idle);
    await actions.adjustShift('08:30', null);
    expect(fakeApi.timer_adjust).not.toHaveBeenCalled();
  });
});

describe('start (§6.2)', () => {
  it('starts with the picked job', async () => {
    setTimer(idle);
    actions.jobDraft.set('Night');
    fakeApi.timer_start.mockResolvedValueOnce({ ok: true, status: 'ok', timer: { ...running, job_shift: 'Night' } });
    let runningAtIgnite: boolean | null = null;
    const unsub = onFx((e) => {
      if (e.kind === 'ignite') runningAtIgnite = get(timer).running;
    });
    await actions.toggleTimer();
    unsub();
    expect(fakeApi.timer_start).toHaveBeenCalledWith('now', null, 'Night', undefined);
    expect(get(timer).running).toBe(true);
    expect(fx).toEqual([{ kind: 'ignite' }]);
    expect(runningAtIgnite).toBe(true);
  });

  it('ok but the timer is not running → no ignite', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({ ok: true, status: 'ok', timer: idle });
    await actions.startShift('now');
    expect(fx).toEqual([]);
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
    expect(fx).toEqual([{ kind: 'ignite' }]);
  });

  it('start_ahead cancelled → no ignite', async () => {
    setTimer(idle);
    const ahead = needs('start_ahead', ['now', 'earlier', 'cancel'], 'now', 'cancel');
    fakeApi.timer_start
      .mockResolvedValueOnce({ ...ahead, confirm: { ...ahead.confirm, token: undefined } })
      .mockResolvedValueOnce({ ok: true, status: 'cancelled', timer: idle });
    script = ['cancel'];
    await actions.startShift('at', '23:30');
    expect(get(timer).running).toBe(false);
    expect(fx).toEqual([]);
  });

  it('invalid start time → alert, no ignite', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({ ok: false, status: 'invalid', field: 'time', message: 'Bad time', timer: idle });
    await actions.startShift('at', '25:00');
    expect(shown.at(-1)?.title).toBe('Invalid start time');
    expect(fx).toEqual([]);
  });

  it('already running → no ignite even though the timer runs', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({
      ok: false,
      status: 'error',
      error: { code: 'already_running', message: 'Already running.' },
      timer: running,
    });
    await actions.startShift('now');
    expect(get(timer).running).toBe(true);
    expect(fx).toEqual([]);
  });

  it('start error → reported, no ignite', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({
      ok: false,
      status: 'error',
      error: { code: 'save_failed', message: 'locked' },
      timer: idle,
    });
    await actions.startShift('now');
    expect(shown.at(-1)?.title).toBe('Could not start the shift');
    expect(fx).toEqual([]);
  });

  it('start dial pre-answers start_ahead and start_backdate with the dialled start', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({ ok: true, status: 'ok', timer: running });
    await actions.startDialShift(new Date(2026, 9, 29, 1, 30).getTime());
    expect(fakeApi.timer_start).toHaveBeenCalledTimes(1);
    expect(fakeApi.timer_start.mock.calls[0].slice(0, 2)).toEqual(['at', '01:30']);
    expect(fakeApi.timer_start.mock.calls[0][3]).toEqual([
      { kind: 'start_ahead', choice: 'earlier' },
      { kind: 'start_backdate', choice: 'earlier' },
    ]);
    expect(shown).toHaveLength(0);
    expect(fx).toEqual([{ kind: 'ignite' }]);
  });

  it('start dial at "now" is a plain start now', async () => {
    setTimer(idle);
    fakeApi.timer_start.mockResolvedValueOnce({ ok: true, status: 'ok', timer: running });
    await actions.startDialShift(null);
    expect(fakeApi.timer_start.mock.calls[0][0]).toBe('now');
    expect(fakeApi.timer_start.mock.calls[0][3]).toBeUndefined();
    expect(fx).toEqual([{ kind: 'ignite' }]);
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
    expect(fx).toEqual([]);
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
    expect(fx).toEqual([{ kind: 'ignite' }]);
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
