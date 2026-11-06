import { describe, expect, it, vi } from 'vitest';

// The bridge picks its backend when imported, so pywebview must be in place first.
const raw = vi.hoisted(() => ({
  bootstrap: vi.fn(async () => ({ ok: true, status: 'ok', data: {} })),
  echo: vi.fn(async (...args: unknown[]) => ({ ok: true, status: 'ok', data: args })),
  nothing: vi.fn(async () => null),
  boom: vi.fn(async () => {
    throw new Error('kaboom');
  }),
  throwsString: vi.fn(() => {
    throw 'plain string';
  }),
}));
vi.stubGlobal('pywebview', { api: raw });

const { api, ready, isMock } = await import('../src/lib/api/bridge');
// Methods outside the typed Api, to reach the bridge's edge cases.
const loose = api as unknown as Record<string, (...args: unknown[]) => Promise<any>>;

describe('bridge', () => {
  it('uses pywebview when it is already injected, not the mock', async () => {
    await ready;
    expect(isMock()).toBe(false);
    await api.bootstrap();
    expect(raw.bootstrap).toHaveBeenCalledOnce();
  });

  it('drops trailing undefined args so Python gets its defaults', async () => {
    const r = await loose.echo(1, undefined, 'x', undefined, undefined);
    expect(raw.echo).toHaveBeenLastCalledWith(1, undefined, 'x');
    expect(r.data).toEqual([1, undefined, 'x']);
    await loose.echo(undefined);
    expect(raw.echo).toHaveBeenLastCalledWith();
  });

  it('turns a missing method into an internal error result', async () => {
    const r = await loose.no_such_method(1);
    expect(r).toEqual({
      ok: false,
      status: 'error',
      error: { code: 'internal', message: 'API method no_such_method is missing' },
    });
  });

  it('never rejects: a throwing method resolves to an internal error', async () => {
    await expect(loose.boom()).resolves.toEqual({
      ok: false,
      status: 'error',
      error: { code: 'internal', message: 'kaboom' },
    });
    await expect(loose.throwsString()).resolves.toMatchObject({
      ok: false,
      error: { code: 'internal', message: 'plain string' },
    });
  });

  it('treats a null result as plain ok', async () => {
    await expect(loose.nothing()).resolves.toEqual({ ok: true, status: 'ok' });
  });

  it('is not thenable, so awaiting the proxy itself is safe', async () => {
    expect((api as unknown as { then?: unknown }).then).toBeUndefined();
    await expect(Promise.resolve(api)).resolves.toBe(api);
  });
});
