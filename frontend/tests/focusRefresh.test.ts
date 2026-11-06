// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MonthData } from '../src/lib/api/types';

const listMonth = vi.fn();
vi.mock('../src/lib/api/bridge', () => ({
  api: { list_month: (...a: unknown[]) => listMonth(...a) },
  ready: Promise.resolve(),
  isMock: () => true,
}));

const { createFocusRefresher, isTyping, startFocusRefresh, FOCUS_REFRESH_MS } = await import('../src/lib/focusRefresh');
const { month } = await import('../src/lib/stores/entries');
const { pushModal } = await import('../src/lib/stores/modals');

const MONTH: MonthData = {
  year: 2026, month: 9, label: 'September 2026', pay_rate: 0, entries: [], weeks: [],
  total_minutes: 0, earnings: 0, holidays: {},
};

describe('createFocusRefresher', () => {
  it('runs at most once per interval', () => {
    let t = 0;
    const refresh = vi.fn();
    const trigger = createFocusRefresher({ refresh, busy: () => false, now: () => t });
    expect(trigger()).toBe(true);
    t = FOCUS_REFRESH_MS - 1;
    expect(trigger()).toBe(false);
    t = FOCUS_REFRESH_MS;
    expect(trigger()).toBe(true);
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it('skips while busy, and a skip does not start the interval', () => {
    let t = 0;
    let busy = true;
    const refresh = vi.fn();
    const trigger = createFocusRefresher({ refresh, busy: () => busy, now: () => t });
    expect(trigger()).toBe(false);
    busy = false;
    t = 1;
    expect(trigger()).toBe(true);
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});

describe('isTyping', () => {
  it('is true for text fields and editable content only', () => {
    const make = (html: string) => {
      const box = document.createElement('div');
      box.innerHTML = html;
      return box.firstElementChild;
    };
    expect(isTyping(null)).toBe(false);
    expect(isTyping(make('<input>'))).toBe(true);
    expect(isTyping(make('<input type="search">'))).toBe(true);
    expect(isTyping(make('<textarea></textarea>'))).toBe(true);
    expect(isTyping(make('<input type="checkbox">'))).toBe(false);
    expect(isTyping(make('<button>x</button>'))).toBe(false);
    const div = make('<div contenteditable="true"></div>') as HTMLElement;
    Object.defineProperty(div, 'isContentEditable', { value: true });
    expect(isTyping(div)).toBe(true);
  });
});

describe('startFocusRefresh', () => {
  let stop: (() => void) | undefined;
  afterEach(() => {
    stop?.();
    stop = undefined;
    month.set(null);
    listMonth.mockReset();
    vi.useRealTimers();
  });

  it('reloads the month on focus and on turning visible, throttled', async () => {
    vi.useFakeTimers({ now: 100_000 });
    listMonth.mockResolvedValue({ ok: true, status: 'ok', data: MONTH });
    month.set(MONTH);
    stop = startFocusRefresh();
    window.dispatchEvent(new Event('focus'));
    await vi.runAllTimersAsync();
    expect(listMonth).toHaveBeenCalledTimes(1);
    document.dispatchEvent(new Event('visibilitychange'));   // jsdom is "visible"
    expect(listMonth).toHaveBeenCalledTimes(1);               // within 5 s
    vi.setSystemTime(100_000 + FOCUS_REFRESH_MS);
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.runAllTimersAsync();
    expect(listMonth).toHaveBeenCalledTimes(2);
  });

  it('does nothing before a month loaded or while a modal is open', () => {
    listMonth.mockResolvedValue({ ok: true, status: 'ok', data: MONTH });
    stop = startFocusRefresh();
    window.dispatchEvent(new Event('focus'));
    expect(listMonth).not.toHaveBeenCalled();
    month.set(MONTH);
    const modal = pushModal(() => {});
    window.dispatchEvent(new Event('focus'));
    expect(listMonth).not.toHaveBeenCalled();
    modal.release();
  });

  it('stops listening once removed', () => {
    month.set(MONTH);
    stop = startFocusRefresh();
    stop();
    window.dispatchEvent(new Event('focus'));
    expect(listMonth).not.toHaveBeenCalled();
  });
});
