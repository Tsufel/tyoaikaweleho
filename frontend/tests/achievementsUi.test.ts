import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Achievement, EntryRow, RecordsData } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({ get_achievements: vi.fn(), ack_achievements: vi.fn(), get_records: vi.fn() }));

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

const ach = await import('../src/lib/stores/achievements');
const AchievementUnlock = (await import('../src/views/achievements/AchievementUnlock.svelte')).default;
const AchievementsSheet = (await import('../src/views/achievements/AchievementsSheet.svelte')).default;
const { settings } = await import('../src/lib/stores/settings');
const { nextUp } = await import('../src/views/achievements/tiers');

function item(id: string): Achievement {
  return {
    id,
    title: `Title ${id}`,
    desc: '',
    icon: id,
    tier: 'gold',
    hidden: false,
    progress: { cur: 1, goal: 1, unit: 'shifts' },
    met_on: '2026-10-01',
  };
}
const card = () => document.querySelector('.unlock');
const NO_RECORDS: RecordsData = {
  total_shifts: 0, first_shift_date: null, days_since_first: null, longest_shift: null, best_day: null,
  best_week: null, most_shifts_week: null, best_month: null, earliest_start: null, latest_finish: null,
  streak: { current: 0, best: 0 },
};
const row = (date: string, time_in: string, time_out: string) =>
  ({ id: date, date, job_shift: 'Sales', time_in, time_out }) as EntryRow;

beforeEach(() => {
  fakeApi.get_achievements.mockReset();
  fakeApi.ack_achievements.mockReset().mockResolvedValue({ ok: true, status: 'ok' });
  fakeApi.get_records.mockReset().mockResolvedValue({ ok: true, status: 'ok', ...NO_RECORDS });
  ach.resetAchievementsSession();
  settings.update((st) => ({ ...st, pay_rate: 20 }));
});
afterEach(() => {
  vi.useRealTimers();
  cleanup();
  document.body.innerHTML = '';
});

describe('AchievementUnlock', () => {
  it('waits while held, acks only when the card shows, and resumes after a modal', async () => {
    vi.useFakeTimers();
    const { rerender } = render(AchievementUnlock, { held: true });
    ach.unlockQueue.set([item('u_a')]);
    await vi.advanceTimersByTimeAsync(3000);
    expect(card()).toBeNull();
    expect(fakeApi.ack_achievements).not.toHaveBeenCalled();

    await rerender({ held: false });
    await vi.advanceTimersByTimeAsync(1000);
    expect(card()?.textContent).toContain('Title u_a');
    expect(fakeApi.ack_achievements).toHaveBeenCalledWith(['u_a']);
    expect(screen.getByRole('status').textContent).toBe('Achievement unlocked: Title u_a');

    // a modal hides it and pauses the countdown
    await rerender({ held: true });
    expect(card()).toBeNull();
    await vi.advanceTimersByTimeAsync(10000);
    expect(get(ach.unlockQueue)).toHaveLength(1);

    await rerender({ held: false });
    expect(card()?.textContent).toContain('Title u_a');
    expect(fakeApi.ack_achievements).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(4700);
    expect(get(ach.unlockQueue)).toEqual([]);
  });

  it('during a shift starts no card, but lets the one already showing finish', async () => {
    vi.useFakeTimers();
    const { rerender } = render(AchievementUnlock, { waiting: false });
    ach.unlockQueue.set([item('w_a'), item('w_b')]);
    await vi.advanceTimersByTimeAsync(1000);
    expect(card()?.textContent).toContain('Title w_a');

    // a shift starts: w_a (already acked) stays up and counts down
    await rerender({ waiting: true });
    expect(card()?.textContent).toContain('Title w_a');
    await vi.advanceTimersByTimeAsync(10000);
    expect(get(ach.unlockQueue).map((a) => a.id)).toEqual(['w_b']);
    expect(card()).toBeNull();
    expect(fakeApi.ack_achievements).toHaveBeenCalledTimes(1);

    // the shift ends: w_b shows
    await rerender({ waiting: false });
    await vi.advanceTimersByTimeAsync(1000);
    expect(card()?.textContent).toContain('Title w_b');
    expect(fakeApi.ack_achievements).toHaveBeenLastCalledWith(['w_b']);
  });

  it('pauses while focused and gives focus back on dismiss', async () => {
    vi.useFakeTimers();
    const outside = document.createElement('button');
    document.body.append(outside);
    render(AchievementUnlock, { held: false });
    ach.unlockQueue.set([item('u_b')]);
    await vi.advanceTimersByTimeAsync(1000);

    outside.focus();
    const close = screen.getByRole('button', { name: 'Dismiss' });
    close.focus();
    await vi.advanceTimersByTimeAsync(10000);
    expect(get(ach.unlockQueue)).toHaveLength(1);

    await fireEvent.click(close);
    expect(get(ach.unlockQueue)).toEqual([]);
    expect(document.activeElement).toBe(outside);
  });

  it('gives focus back when a modal hid the card while it had focus', async () => {
    vi.useFakeTimers();
    const outside = document.createElement('button');
    document.body.append(outside);
    const { rerender } = render(AchievementUnlock, { held: false });
    ach.unlockQueue.set([item('u_c')]);
    await vi.advanceTimersByTimeAsync(1000);
    outside.focus();
    screen.getByRole('button', { name: 'Dismiss' }).focus();

    await rerender({ held: true });
    expect(card()).toBeNull();
    (document.activeElement as HTMLElement | null)?.blur(); // the modal's restore target is gone
    await rerender({ held: false });
    await tick();
    expect(document.activeElement).toBe(outside);
  });
});

describe('AchievementsSheet', () => {
  it('shows the error with Retry after a failed load, then the list', async () => {
    fakeApi.get_achievements.mockRejectedValueOnce(new Error('bridge gone'));
    render(AchievementsSheet, { onclose: () => {} });
    const retry = await screen.findByRole('button', { name: 'Retry' });
    expect(screen.getByText("Couldn't load achievements.")).toBeTruthy();

    // a failed retry: Retry stays mounted and focused throughout
    let fail!: () => void;
    fakeApi.get_achievements.mockImplementationOnce(() => new Promise((_, rej) => (fail = () => rej(new Error('still gone')))));
    retry.focus();
    await fireEvent.click(retry);
    expect(retry.isConnected).toBe(true);
    expect(retry.textContent).toContain('Retrying');
    expect(document.activeElement).toBe(retry);
    fail();
    await vi.waitFor(() => expect(retry.textContent).toContain('Retry'));
    await tick();
    expect(retry.textContent).not.toContain('Retrying');
    expect(document.activeElement).toBe(retry);

    // a successful one: the list replaces it and focus moves to the summary, not <body>
    let pass!: () => void;
    fakeApi.get_achievements.mockImplementationOnce(
      () => new Promise((r) => (pass = () => r({ ok: true, status: 'ok', items: [item('s_a')], newly: [], first_run: false }))),
    );
    await fireEvent.click(retry);
    expect(document.activeElement).toBe(retry);
    pass();
    expect(await screen.findByText('Title s_a')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Retry/ })).toBeNull();
    expect(document.activeElement).toBe(document.querySelector('.summary'));
  });

  it('keeps the last data when a later check fails', async () => {
    ach.achievements.set({ items: [item('s_b')], newly: [], first_run: false });
    ach.achievementsError.set("Couldn't load achievements.");
    render(AchievementsSheet, { onclose: () => {} });
    expect(await screen.findByText('Title s_b')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  });

  it('shows the Hall of fame from get_records, and re-asks with achievements', async () => {
    ach.achievements.set({ items: [item('h_a')], newly: [], first_run: false });
    fakeApi.get_records.mockResolvedValueOnce({
      ok: true, status: 'ok', ...NO_RECORDS, total_shifts: 12, first_shift_date: '2026-03-02', days_since_first: 240,
      longest_shift: { entry: row('2026-10-07', '18:00', '04:30'), minutes: 630 },
      best_week: { key: '2026-W41', start: '2026-10-05', minutes: 2580 },
      latest_finish: { entry: row('2026-10-07', '18:00', '04:30'), time: '04:30', next_day: true },
      streak: { current: 0, best: 4 },
    });
    render(AchievementsSheet, { onclose: () => {} });
    const panel = await screen.findByRole('region', { name: 'Hall of fame' });
    expect(panel.textContent).toContain('Longest shift');
    expect(panel.textContent).toContain('10h 30m');
    expect(panel.textContent).toContain('7.10.2026 · Sales');
    expect(panel.textContent).toContain('Week 41, from 5.10.2026');
    expect(panel.textContent).toContain('04:30 +1');
    expect(panel.textContent).toContain('4 workdays');
    expect(panel.textContent).toContain('2.3.2026');
    expect(panel.textContent).not.toContain('Best month');

    ach.achievements.set({ items: [item('h_a'), item('h_b')], newly: [], first_run: false });
    await vi.waitFor(() => expect(fakeApi.get_records).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Your records show up here after your first shift.')).toBeTruthy();
  });

  it('leaves the Hall of fame out when get_records fails', async () => {
    fakeApi.get_records.mockReset().mockRejectedValue(new Error('bridge gone'));
    ach.achievements.set({ items: [item('h_c')], newly: [], first_run: false });
    render(AchievementsSheet, { onclose: () => {} });
    expect(await screen.findByText('Title h_c')).toBeTruthy();
    await tick();
    expect(screen.queryByRole('region', { name: 'Hall of fame' })).toBeNull();
  });
});

const locked = (id: string, cur: number, goal: number, more: Partial<Achievement> = {}): Achievement => ({
  ...item(id),
  met_on: null,
  progress: { cur, goal, unit: 'h' },
  ...more,
});

describe('nextUp', () => {
  it('picks the locked badge closest to its goal, the lower tier on a tie', () => {
    const items = [
      item('done'),
      locked('far', 10, 100),
      locked('near_gold', 80, 100),
      locked('near_silver', 8, 10, { tier: 'silver' }),
      locked('secret', 99, 100, { hidden: true }),
      locked('binary', 0, 1),
    ];
    expect(nextUp(items, 20)?.id).toBe('near_silver');
    expect(nextUp(items.slice(0, 2), 20)?.id).toBe('far');
  });

  it('skips untouched badges, and earnings without a pay rate', () => {
    const cash = locked('cash', 900, 1000, { progress: { cur: 900, goal: 1000, unit: '€' } });
    expect(nextUp([locked('zero', 0, 10), cash], 20)?.id).toBe('cash');
    expect(nextUp([locked('zero', 0, 10), cash], 0)).toBeNull();
  });
});

describe('AchievementsSheet extras', () => {
  it('shows the next-up strip, and a pay rate hint on earnings when the rate is 0', async () => {
    const cash = locked('cash', 0, 1000, { title: 'Cash', progress: { cur: 0, goal: 1000, unit: '€' } });
    ach.achievements.set({ items: [item('x_done'), locked('x_next', 40, 100, { title: 'Hundred' }), cash], newly: [], first_run: false });
    settings.update((st) => ({ ...st, pay_rate: 0 }));
    render(AchievementsSheet, { onclose: () => {} });
    const strip = await vi.waitFor(() => {
      const el = document.querySelector('.next');
      if (!el) throw new Error('no strip');
      return el;
    });
    expect(strip.textContent).toContain('Next up');
    expect(strip.textContent).toContain('Hundred');
    expect(strip.textContent).toContain('40 / 100 h');
    expect(screen.getByText('Set your pay rate in Settings to start counting earnings.')).toBeTruthy();

    settings.update((st) => ({ ...st, pay_rate: 20 }));
    await tick();
    expect(screen.queryByText('Set your pay rate in Settings to start counting earnings.')).toBeNull();
  });

  it('tells screen readers what is locked and how many are unlocked', async () => {
    ach.achievements.set({ items: [item('y_done'), locked('y_locked', 3, 10)], newly: [], first_run: false });
    render(AchievementsSheet, { onclose: () => {} });
    const bar = await screen.findByRole('progressbar', { name: 'Achievements unlocked' });
    expect(bar.getAttribute('aria-valuetext')).toBe('1 of 2 unlocked');
    const cards = [...document.querySelectorAll('.card')];
    expect(cards.map((c) => c.querySelector('.sr-only')?.textContent)).toEqual(['Unlocked:', 'Locked:']);
    expect(cards[1].querySelector('.track')?.getAttribute('aria-hidden')).toBe('true');
  });
});
