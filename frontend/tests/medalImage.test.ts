import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// 2.1.7: a colleague's Achievements showed every hidden ("???") Silver card as
// a broken image. All of a tier's hidden cards share one file, so one failed
// load broke them all for good. A medal that fails now retries once under a
// fresh URL, then shows a placeholder and logs the URL.
const fakeApi = vi.hoisted(() => ({ log_client_error: vi.fn(async () => ({ ok: true })) }));
vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));

const { MEDAL_PLACEHOLDER, RETRY_DELAY_MS, medalImg, resetMedalLog, retryUrl } = await import(
  '../src/lib/medalImage'
);
const { medalUrl } = await import('../src/lib/stores/achievements');

const URL_A = 'http://127.0.0.1:42001/assets/hidden_silver-XfBLSsK_.webp';
const URL_B = 'http://127.0.0.1:42001/assets/hours_100-CRIWtgxG.webp';

const logged = () => fakeApi.log_client_error.mock.calls.map((c) => String((c as unknown[])[0]));
const fail = (img: HTMLImageElement) => img.dispatchEvent(new Event('error'));

beforeEach(() => {
  vi.useFakeTimers();
  fakeApi.log_client_error.mockClear();
  resetMedalLog();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('medalImg', () => {
  it('sets the medal url', () => {
    const img = document.createElement('img');
    medalImg(img, URL_A);
    expect(img.src).toBe(URL_A);
  });

  it('retries a failed medal once under a fresh url', () => {
    const img = document.createElement('img');
    medalImg(img, URL_A);
    fail(img);
    expect(img.src).toBe(URL_A); // waits a moment first
    vi.advanceTimersByTime(RETRY_DELAY_MS);
    expect(img.src).toMatch(/^http:\/\/127\.0\.0\.1:42001\/assets\/hidden_silver-XfBLSsK_\.webp\?r=\d+$/);
    expect(logged()).toEqual([]); // a retry that works is not an error
  });

  it('shows the placeholder and logs the url when the retry fails too', () => {
    const img = document.createElement('img');
    medalImg(img, URL_A);
    fail(img);
    vi.advanceTimersByTime(RETRY_DELAY_MS);
    fail(img);
    expect(img.src).toBe(MEDAL_PLACEHOLDER);
    expect(logged()).toEqual([`Medal image failed to load: ${URL_A} (after one retry)`]);
    fail(img); // the placeholder itself failing never loops
    vi.advanceTimersByTime(RETRY_DELAY_MS * 5);
    expect(img.src).toBe(MEDAL_PLACEHOLDER);
    expect(logged()).toHaveLength(1);
  });

  it('logs each url once, however many cards share it', () => {
    for (let i = 0; i < 3; i++) {
      const img = document.createElement('img');
      medalImg(img, URL_A);
      fail(img);
      vi.advanceTimersByTime(RETRY_DELAY_MS);
      fail(img);
      expect(img.src).toBe(MEDAL_PLACEHOLDER);
    }
    expect(logged()).toHaveLength(1);
  });

  it('shows the placeholder at once for an empty url', () => {
    const img = document.createElement('img');
    medalImg(img, '');
    expect(img.src).toBe(MEDAL_PLACEHOLDER);
    expect(logged()).toEqual(['Medal image failed to load: (no url) (after one retry)']);
  });

  it('starts over when the url changes', () => {
    const img = document.createElement('img');
    const action = medalImg(img, URL_A);
    fail(img);
    action.update(URL_B);
    vi.advanceTimersByTime(RETRY_DELAY_MS); // the old retry is dropped
    expect(img.src).toBe(URL_B);
    fail(img);
    vi.advanceTimersByTime(RETRY_DELAY_MS);
    expect(img.src).toMatch(/hours_100-CRIWtgxG\.webp\?r=\d+$/); // a first failure again
    expect(logged()).toEqual([]);
  });

  it('a placeholder medal gets its image back when the url changes', () => {
    const img = document.createElement('img');
    const action = medalImg(img, '');
    action.update(URL_B);
    expect(img.src).toBe(URL_B);
  });

  it('stops retrying once destroyed', () => {
    const img = document.createElement('img');
    const action = medalImg(img, URL_A);
    fail(img);
    action.destroy();
    vi.advanceTimersByTime(RETRY_DELAY_MS);
    expect(img.src).toBe(URL_A);
    fail(img);
    expect(img.src).toBe(URL_A);
    expect(logged()).toEqual([]);
  });
});

describe('retryUrl', () => {
  it('adds a cache-busting query', () => {
    expect(retryUrl('/assets/a.webp', 7)).toBe('/assets/a.webp?r=7');
    expect(retryUrl('/assets/a.webp?v=1', 7)).toBe('/assets/a.webp?v=1&r=7');
  });
});

describe('medalUrl for hidden cards', () => {
  it('every tier has hidden art', () => {
    for (const tier of ['bronze', 'silver', 'gold', 'legendary'] as const) {
      const url = medalUrl({ icon: 'early_bird', tier, hidden: true, met_on: null });
      expect(url, tier).toMatch(new RegExp(`hidden_${tier}`));
    }
  });

  it('a met hidden achievement shows its own medal', () => {
    expect(medalUrl({ icon: 'early_bird', tier: 'silver', hidden: true, met_on: '2026-10-01' })).toMatch(
      /early_bird/,
    );
  });
});
