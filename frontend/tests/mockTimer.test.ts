import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createMockApi } from '../src/lib/api/mock';
import type { Api, ConfirmList } from '../src/lib/api/types';

// The mock mirrors webapp/controller.py for the timer and recovery flows.
let api: Api;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 8, 23, 10, 0, 0));
  api = createMockApi();
});
afterEach(() => {
  vi.useRealTimers();
});

const mock = () => window.__welehoMock!;

describe('mock timer_discard', () => {
  it('is not_running when no shift runs', async () => {
    const r = await api.timer_discard();
    expect(r.ok).toBe(false);
    expect(r.status).toBe('error');
    if (r.status === 'error') expect(r.error.code).toBe('not_running');
  });
});

describe('mock timer_stop limits go by the clock', () => {
  it('asks over_24h when the clock says 24h even if a few seconds short', async () => {
    // started 09:00:30 yesterday, now 09:00:10 → 23h59m50s elapsed, 1440 clock minutes
    vi.setSystemTime(new Date(2026, 8, 23, 9, 0, 10));
    mock().setRunning((24 * 3600 - 20) / 3600);
    const r = await api.timer_stop('button');
    expect(r.status).toBe('needs_confirm');
    if (r.status === 'needs_confirm') expect(r.confirm.kind).toBe('over_24h');
  });
});

describe('mock recovery_resolve save', () => {
  beforeEach(() => {
    mock().setRecovery(2); // started 08:00
  });

  it('rejects an end time equal to the start', async () => {
    const r = await api.recovery_resolve('save', '08:00');
    expect(r.status).toBe('invalid');
    if (r.status === 'invalid') {
      expect(r.field).toBe('end');
      expect(r.message).toContain('08:00');
    }
    expect(r.recovery).not.toBeNull();
  });

  it('asks before saving a long shift, and cancel keeps it pending', async () => {
    const ask = await api.recovery_resolve('save', '06:30');
    expect(ask.status).toBe('needs_confirm');
    if (ask.status !== 'needs_confirm') return;
    expect(ask.confirm.kind).toBe('long_entry');
    const token = ask.confirm.token;
    expect(token).toBeTruthy();

    const cancel: ConfirmList = [{ kind: 'long_entry', choice: 'cancel', token }];
    const r1 = await api.recovery_resolve('save', '06:30', cancel);
    expect(r1.status).toBe('cancelled');
    expect(r1.recovery).not.toBeNull();

    const stale: ConfirmList = [{ kind: 'long_entry', choice: 'save', token: 'nope' }];
    const r2 = await api.recovery_resolve('save', '06:30', stale);
    expect(r2.status).toBe('error');

    const save: ConfirmList = [{ kind: 'long_entry', choice: 'save', token }];
    const r3 = await api.recovery_resolve('save', '06:30', save);
    expect(r3.status).toBe('saved');
    expect(r3.recovery).toBeNull();
  });

  it('saves a normal end time straight away', async () => {
    const r = await api.recovery_resolve('save', '09:45');
    expect(r.status).toBe('saved');
  });
});
