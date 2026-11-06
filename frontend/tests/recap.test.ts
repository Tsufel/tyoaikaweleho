import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Achievement, EntryRow, StatsData } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({ get_stats: vi.fn() }));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/lib/stores/entries', async () => {
  const { writable } = await import('svelte/store');
  return { month: writable(null) };
});
vi.mock('../src/lib/stores/settings', async () => {
  const { writable } = await import('svelte/store');
  // Reduced motion: transitions are instant, so jsdom needs no Web Animations.
  return { settings: writable({ pay_rate: 20, ui_prefs: { target_hours: 8, reduce_effects: true, lulz: false } }) };
});

const { RECAP_KEY, buildRecap, lastWeek, readShownWeek, writeShownWeek } = await import('../src/views/recap/recap');
const { unlockQueue } = await import('../src/lib/stores/achievements');
const WeeklyRecap = (await import('../src/views/recap/WeeklyRecap.svelte')).default;

type Totals = StatsData['totals'];
const totals = (t: Partial<Totals> = {}): Totals => ({ minutes: 1935, earnings: 645, shifts: 4, worked_days: 4, ...t });
const longest = (date: string, minutes: number) => ({ entry: { date } as EntryRow, minutes });
const stats = (t: Partial<Totals> = {}, pay_rate = 20) => ({
  ok: true,
  status: 'ok',
  data: { totals: totals(t), longest: longest('2026-10-28', 600), pay_rate },
});

describe('recap helpers', () => {
  it('finds the whole ISO week before today, across a new year too', () => {
    expect(lastWeek(new Date(2026, 10, 4))).toEqual({
      key: '2026-W44',
      week: 44,
      range: { start: '2026-10-26', end: '2026-11-01' },
    });
    expect(lastWeek(new Date(2026, 10, 2)).key).toBe('2026-W44');
    expect(lastWeek(new Date(2026, 10, 1)).key).toBe('2026-W43');
    expect(lastWeek(new Date(2026, 0, 2))).toMatchObject({ key: '2025-W52', range: { start: '2025-12-22', end: '2025-12-28' } });
  });

  it('builds the card text, and nothing for an empty week', () => {
    const week = lastWeek(new Date(2026, 10, 4));
    const r = buildRecap(week, { totals: totals(), longest: longest('2026-10-28', 600) }, 20)!;
    expect(r.title).toBe('Week 44 in review');
    expect(r.range).toBe('26 Oct – 1 Nov 2026');
    expect(r.stats).toEqual([
      { label: 'Worked', value: '32h 15m' },
      { label: 'Shifts', value: '4' },
      { label: 'Days', value: '4' },
      { label: 'Earned', value: '€645.00' },
    ]);
    expect(r.note).toBe('Longest shift 10h 00m, on Wednesday.');

    const one = buildRecap(week, { totals: totals({ shifts: 1, worked_days: 1, minutes: 60 }), longest: longest('2026-10-28', 60) }, 0)!;
    expect(one.stats.map((s) => s.label)).toEqual(['Worked', 'Shifts', 'Days']);
    expect(one.note).toBe('1 shift done. Nice one.');

    expect(buildRecap(week, { totals: totals({ shifts: 0, minutes: 0, worked_days: 0 }), longest: null }, 20)).toBeNull();
  });

  it('survives storage that throws', () => {
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(readShownWeek()).toBeNull();
    expect(() => writeShownWeek('2026-W44')).not.toThrow();
    get.mockRestore();
    set.mockRestore();
  });
});

describe('WeeklyRecap', () => {
  const week = lastWeek(new Date());

  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    unlockQueue.set([]);
    fakeApi.get_stats.mockReset();
    fakeApi.get_stats.mockResolvedValue(stats());
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  const card = () => document.querySelector('.recap');

  it('shows last week once, then remembers the week', async () => {
    render(WeeklyRecap);
    await vi.advanceTimersByTimeAsync(2000);
    expect(fakeApi.get_stats).toHaveBeenCalledWith(week.range.start, week.range.end, 'day');
    expect(card()).toBeTruthy();
    expect(screen.getByText(`Week ${week.week} in review`)).toBeTruthy();
    expect(screen.getByText('32h 15m')).toBeTruthy();
    expect(localStorage.getItem(RECAP_KEY)).toBe(week.key);

    await fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    await vi.advanceTimersByTimeAsync(500);
    expect(card()).toBeNull();

    cleanup();
    render(WeeklyRecap);
    await vi.advanceTimersByTimeAsync(2000);
    expect(fakeApi.get_stats).toHaveBeenCalledTimes(1);
    expect(card()).toBeNull();
  });

  it('skips an empty week without showing anything', async () => {
    fakeApi.get_stats.mockResolvedValue(stats({ shifts: 0, minutes: 0, worked_days: 0, earnings: 0 }));
    render(WeeklyRecap);
    await vi.advanceTimersByTimeAsync(2000);
    expect(card()).toBeNull();
    expect(localStorage.getItem(RECAP_KEY)).toBe(week.key);
  });

  it('does not remember the week when loading fails', async () => {
    fakeApi.get_stats.mockRejectedValue(new Error('down'));
    render(WeeklyRecap);
    await vi.advanceTimersByTimeAsync(2000);
    expect(card()).toBeNull();
    expect(localStorage.getItem(RECAP_KEY)).toBeNull();
  });

  it('waits for modals, shifts and unlock cards', async () => {
    const view = render(WeeklyRecap, { held: true });
    await vi.advanceTimersByTimeAsync(3000);
    expect(card()).toBeNull();
    expect(localStorage.getItem(RECAP_KEY)).toBeNull();

    await view.rerender({ held: false, waiting: true });
    await vi.advanceTimersByTimeAsync(3000);
    expect(card()).toBeNull();

    unlockQueue.set([{ id: 'x' } as Achievement]);
    await view.rerender({ held: false, waiting: false });
    await vi.advanceTimersByTimeAsync(3000);
    expect(card()).toBeNull();

    unlockQueue.set([]);
    await vi.advanceTimersByTimeAsync(2000);
    expect(card()).toBeTruthy();
    expect(localStorage.getItem(RECAP_KEY)).toBe(week.key);
  });
});
