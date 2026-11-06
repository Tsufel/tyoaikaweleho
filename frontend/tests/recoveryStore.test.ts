import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Recovery, TimerState } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({ get_recovery: vi.fn(), bootstrap: vi.fn() }));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/lib/stores/entries', () => ({
  showEntry: vi.fn(),
  refreshMonth: vi.fn(),
  setViewMonth: vi.fn(),
}));

const { offerRecovery, pendingRecovery } = await import('../src/lib/stores/recovery');
const { IDLE_TIMER, timer } = await import('../src/lib/stores/timer');
const { toasts, clearToasts } = await import('../src/lib/stores/toasts');

const rec: Recovery = {
  start_iso: '2026-10-29T09:00:00',
  start_epoch_ms: 0,
  job_shift: 'Support',
  elapsed_minutes: 60,
  over_limit: false,
  suggested_end: '10:00',
};
const pending: TimerState = { ...IDLE_TIMER, recovery_pending: true };

describe('offerRecovery', () => {
  beforeEach(() => {
    fakeApi.get_recovery.mockReset();
    fakeApi.bootstrap.mockReset();
    pendingRecovery.set(null);
    clearToasts();
  });

  it('re-reads through get_recovery, never bootstrap', async () => {
    fakeApi.get_recovery.mockResolvedValue({ ok: true, status: 'ok', recovery: rec, timer: pending, data_recovery: null });
    await offerRecovery();
    expect(fakeApi.bootstrap).not.toHaveBeenCalled();
    expect(get(pendingRecovery)).toEqual(rec);
    expect(get(timer).recovery_pending).toBe(true);
    expect(get(toasts)).toHaveLength(0);
  });

  it('shows a data.json repair that happened since bootstrap', async () => {
    fakeApi.get_recovery.mockResolvedValue({
      ok: true,
      status: 'ok',
      recovery: null,
      timer: IDLE_TIMER,
      data_recovery: { source: 'C:\\data\\data.json.bak', damaged_copy: '' },
    });
    await offerRecovery();
    const [t] = get(toasts);
    expect(t.message).toContain('restored from a backup (data.json.bak)');
    expect(t.tone).toBe('warning');
  });

  it('uses a recovery it is given without asking the backend', async () => {
    await offerRecovery(rec);
    expect(fakeApi.get_recovery).not.toHaveBeenCalled();
    expect(get(pendingRecovery)).toEqual(rec);
  });
});
