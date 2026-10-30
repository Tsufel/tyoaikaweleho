import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Achievement } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({ get_achievements: vi.fn(), ack_achievements: vi.fn() }));

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

beforeEach(() => {
  fakeApi.get_achievements.mockReset();
  fakeApi.ack_achievements.mockReset().mockResolvedValue({ ok: true, status: 'ok' });
  ach.resetAchievementsSession();
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
});
