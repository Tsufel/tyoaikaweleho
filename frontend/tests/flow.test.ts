// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ConfirmList, ConfirmRequest, Result } from '../src/lib/api/types';

const confirm = vi.hoisted(() => vi.fn());
vi.mock('../src/lib/stores/confirm', () => ({ confirm }));

const { runFlow } = await import('../src/lib/api/flow');

const ok: Result = { ok: true, status: 'ok' };
const ask = (kind: string, token?: string) =>
  ({
    ok: false,
    status: 'needs_confirm',
    confirm: { kind, title: 't', message: 'm', options: [], ...(token === undefined ? {} : { token }) },
  }) as unknown as Result;

beforeEach(() => {
  confirm.mockReset();
});

describe('runFlow', () => {
  it('calls once with undefined when nothing needs confirming', async () => {
    const call = vi.fn(async (_c: ConfirmList) => ok);
    await expect(runFlow(call)).resolves.toBe(ok);
    expect(call).toHaveBeenCalledOnce();
    expect(call.mock.calls[0][0]).toBeUndefined();
    expect(confirm).not.toHaveBeenCalled();
  });

  it('re-calls with every answer so far, with the token only when there is one', async () => {
    const replies = [ask('overlap'), ask('stale', 'abc'), ok];
    const call = vi.fn(async (_c: ConfirmList) => replies.shift()!);
    confirm.mockResolvedValueOnce('save').mockResolvedValueOnce('reload');
    await runFlow(call);
    expect(call).toHaveBeenCalledTimes(3);
    expect(call.mock.calls[1][0]).toEqual([{ kind: 'overlap', choice: 'save' }]);
    expect(call.mock.calls[2][0]).toEqual([
      { kind: 'overlap', choice: 'save' },
      { kind: 'stale', choice: 'reload', token: 'abc' },
    ]);
    expect((confirm.mock.calls[1][0] as ConfirmRequest).kind).toBe('stale');
  });

  it('passes a fresh copy each round, so earlier lists stay as they were', async () => {
    confirm.mockResolvedValue('x');
    const replies = [ask('a'), ask('b'), ok];
    const seen: ConfirmList[] = [];
    await runFlow(async (c) => {
      if (c) seen.push(c);
      return replies.shift()!;
    });
    expect(seen.map((c) => c.length)).toEqual([1, 2]);
    expect(seen[0]).not.toBe(seen[1]);
  });

  it('sends preset answers on the first call', async () => {
    const call = vi.fn(async (_c: ConfirmList) => ok);
    const preset = [{ kind: 'overlap', choice: 'save' }] as ConfirmList;
    await runFlow(call, preset);
    expect(call.mock.calls[0][0]).toEqual(preset);
    expect(call.mock.calls[0][0]).not.toBe(preset);
  });

  it('gives up after 12 questions and returns the last needs_confirm', async () => {
    confirm.mockResolvedValue('keep');
    const call = vi.fn(async (_c: ConfirmList) => ask('loop'));
    const r = await runFlow(call);
    expect(r.status).toBe('needs_confirm');
    expect(call).toHaveBeenCalledTimes(13);
    expect(confirm).toHaveBeenCalledTimes(12);
  });

  it('returns errors as they are', async () => {
    const err = { ok: false, status: 'error', error: { code: 'save_failed', message: 'disk' } } as Result;
    await expect(runFlow(async () => err)).resolves.toBe(err);
  });
});
