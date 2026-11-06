import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// 2.1.6: "Stats, Pet and Achievements won't open, restarting doesn't help".
// The page was an older UI (from the cache) whose lazy chunks the update had
// deleted. A chunk that won't load now reloads the page once; only a failure
// right after that reload (really broken files) says so, and every failure is
// logged instead of the click doing nothing.
const fakeApi = vi.hoisted(() => ({ log_client_error: vi.fn(async () => ({ ok: true })) }));
vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/views/achievements/AchievementsSheet.svelte', () => {
  throw new Error('Failed to fetch dynamically imported module: AchievementsSheet-x.js');
});
vi.mock('../src/views/pet/PetSheet.svelte', () => {
  throw new Error('Unable to preload CSS for /assets/PetSheet-x.css');
});

const { importOrReload, loadView, page, reloadForStaleChunk, RELOAD_WINDOW_MS } = await import('../src/lib/lazyView');
const { pushModal } = await import('../src/lib/stores/modals');
const { registerEditGuard } = await import('../src/lib/stores/editGuard');
const { openAchievements } = await import('../src/lib/stores/achievements');
const { openPetSheet } = await import('../src/views/pet/petState');
const { dialogs } = await import('../src/lib/stores/confirm');
const { clearToasts, toasts } = await import('../src/lib/stores/toasts');

const KEY = 'weleho-chunk-reload';
let reload: ReturnType<typeof vi.fn<() => void>>;

beforeEach(() => {
  vi.clearAllMocks();
  fakeApi.log_client_error.mockReset().mockImplementation(async () => ({ ok: true }));
  clearToasts();
  sessionStorage.clear();
  reload = vi.fn<() => void>();
  page.reload = reload;
});

afterEach(() => {
  vi.restoreAllMocks();
});

const lastToast = () => get(toasts).at(-1);
const logged = () => fakeApi.log_client_error.mock.calls.map((c) => String((c as unknown[])[0]));
/** As if this page is the one a failed chunk just reloaded. */
const justReloaded = () => sessionStorage.setItem(KEY, String(Date.now()));
const fail = () => Promise.reject(new Error('boom'));

describe('loadView', () => {
  it('returns the default export when the chunk loads', async () => {
    const View = {};
    expect(await loadView('X', 'x', async () => ({ default: View }))).toBe(View);
    expect(get(toasts)).toHaveLength(0);
    expect(fakeApi.log_client_error).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
  });

  it('reloads the page once on the first failure, logging why', async () => {
    expect(await loadView('Stats', 'Stats', fail)).toBeNull();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(get(toasts)).toHaveLength(0);
    expect(logged()).toEqual(['Could not load the Stats chunk, reloading the page: boom']);
    expect(Number(sessionStorage.getItem(KEY))).toBeGreaterThan(0);
  });

  it('a failure right after that reload toasts and logs instead of reloading again', async () => {
    justReloaded();
    expect(await loadView('Stats', 'Stats', fail)).toBeNull();
    expect(reload).not.toHaveBeenCalled();
    expect(lastToast()?.message).toBe("Couldn't open Stats. If this keeps happening, reinstall Weleho.");
    expect(lastToast()?.tone).toBe('error');
    expect(logged()).toEqual(['Could not load the Stats chunk: boom']);
  });

  it('never loops: two failures in a row reload only once', async () => {
    await loadView('Stats', 'Stats', fail);
    await loadView('Stats', 'Stats', fail);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(lastToast()?.message).toMatch(/Couldn't open Stats/);
  });

  it('reloads again once the window has passed (a later update)', async () => {
    sessionStorage.setItem(KEY, String(Date.now() - RELOAD_WINDOW_MS - 1));
    await loadView('Stats', 'Stats', fail);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("doesn't reload when it can't remember having reloaded", async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage off');
    });
    expect(await loadView('Stats', 'Stats', fail)).toBeNull();
    expect(reload).not.toHaveBeenCalled();
    expect(lastToast()?.message).toMatch(/Couldn't open Stats/);
  });

  it('still reloads, and later toasts, when logging itself throws', async () => {
    fakeApi.log_client_error.mockImplementation(() => {
      throw new Error('no bridge');
    });
    expect(await loadView('X', 'x', () => Promise.reject('nope'))).toBeNull();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(await loadView('X', 'x', () => Promise.reject('nope'))).toBeNull();
    expect(lastToast()?.message).toMatch(/Couldn't open x/);
  });

  it("doesn't wait on a log call that never answers", async () => {
    vi.useFakeTimers();
    try {
      fakeApi.log_client_error.mockImplementationOnce(() => new Promise(() => {}));
      const r = reloadForStaleChunk('Stats', new Error('boom'));
      await vi.advanceTimersByTimeAsync(600);
      expect(await r).toBe('reloading');
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('never reloads over open work', () => {
  it('an open dialog: no reload, says to close it, and the next try (closed) reloads', async () => {
    const modal = pushModal(() => {});
    try {
      expect(await loadView('Achievements', 'achievements', fail)).toBeNull();
      expect(reload).not.toHaveBeenCalled();
      expect(sessionStorage.getItem(KEY)).toBeNull();
      expect(lastToast()?.message).toBe("Couldn't open achievements right now. Close what's open, then try again.");
      expect(logged()).toEqual(['Could not load the Achievements chunk: boom']);
    } finally {
      modal.release();
    }
    await loadView('Achievements', 'achievements', fail);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("an inline edit that can't be saved: no reload", async () => {
    const off = registerEditGuard(() => false);
    try {
      await loadView('Pet', "the pet's details", fail);
      expect(reload).not.toHaveBeenCalled();
      expect(lastToast()?.message).toMatch(/right now/);
    } finally {
      off();
    }
  });

  it('an inline edit that saves is committed before the reload', async () => {
    const guard = vi.fn(async () => true);
    const off = registerEditGuard(guard);
    try {
      await loadView('Pet', "the pet's details", fail);
      expect(guard).toHaveBeenCalledTimes(1);
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      off();
    }
  });
});

describe('importOrReload (the Stats route)', () => {
  const settled = (p: Promise<unknown>) =>
    Promise.race([p.then(() => 'settled', () => 'settled'), new Promise((r) => setTimeout(() => r('pending'), 50))]);

  it('resolves the module when it loads', async () => {
    const mod = { default: {} };
    expect(await importOrReload('Stats', async () => mod)).toBe(mod);
    expect(reload).not.toHaveBeenCalled();
  });

  it('first failure: reloads and stays pending, so the spinner stays up', async () => {
    const p = importOrReload('Stats', fail);
    expect(await settled(p)).toBe('pending');
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('failure right after the reload: rethrows for the error card, no second reload', async () => {
    justReloaded();
    await expect(importOrReload('Stats', fail)).rejects.toThrow('boom');
    expect(reload).not.toHaveBeenCalled();
  });
});

describe('sheets that fail to load', () => {
  it('Achievements: reloads once, then toast + log; never a dialog or a rejection', async () => {
    await expect(openAchievements()).resolves.toBeUndefined();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(logged()[0]).toMatch(/^Could not load the Achievements chunk, reloading the page: \S/);
    await expect(openAchievements()).resolves.toBeUndefined();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(lastToast()?.message).toMatch(/Couldn't open achievements/);
    expect(logged()[1]).toMatch(/^Could not load the Achievements chunk: \S/);
    expect(get(dialogs)).toHaveLength(0);
  });

  it("Pet: reloads once, then toast + log; never a dialog or a rejection", async () => {
    await expect(openPetSheet()).resolves.toBeUndefined();
    expect(reload).toHaveBeenCalledTimes(1);
    justReloaded();
    await expect(openPetSheet()).resolves.toBeUndefined();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(lastToast()?.message).toMatch(/Couldn't open the pet's details/);
    expect(logged()[1]).toMatch(/^Could not load the Pet chunk: \S/);
    expect(get(dialogs)).toHaveLength(0);
  });
});
