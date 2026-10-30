import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Achievement, AchievementsData } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({ get_achievements: vi.fn(), ack_achievements: vi.fn() }));
const fakeStores = vi.hoisted(() => ({ month: null as any, settings: null as any }));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/lib/stores/entries', async () => {
  const { writable } = await import('svelte/store');
  fakeStores.month = writable(null);
  return { month: fakeStores.month };
});
vi.mock('../src/lib/stores/settings', async () => {
  const { writable } = await import('svelte/store');
  fakeStores.settings = writable({ pay_rate: 20, ui_prefs: { target_hours: 8 } });
  return { settings: fakeStores.settings };
});

const ach = await import('../src/lib/stores/achievements');
const { toasts, clearToasts, runUndo } = await import('../src/lib/stores/toasts');

function item(id: string, met_on: string | null = '2026-10-01'): Achievement {
  return {
    id,
    title: id,
    desc: '',
    icon: id,
    tier: 'bronze',
    hidden: false,
    progress: { cur: 1, goal: 1, unit: 'shifts' },
    met_on,
  };
}
const ok = (d: AchievementsData) => ({ ok: true, status: 'ok', ...d });

beforeEach(() => {
  fakeApi.get_achievements.mockReset();
  fakeApi.ack_achievements.mockReset().mockResolvedValue({ ok: true, status: 'ok' });
  clearToasts();
  ach.resetAchievementsSession();
});
afterEach(() => vi.useRealTimers());

describe('checkAchievements', () => {
  it('first run: one summary toast, acks everything, no unlock parade', async () => {
    fakeApi.ack_achievements.mockResolvedValueOnce({ ok: false, status: 'error' });
    fakeApi.get_achievements.mockResolvedValue(
      ok({ items: [item('fr_a'), item('fr_b')], newly: ['fr_a', 'fr_b'], first_run: true }),
    );
    await ach.checkAchievements();
    expect(get(toasts).map((t) => t.message)).toEqual(["🏆 You've already earned 2 achievements"]);
    expect(fakeApi.ack_achievements).toHaveBeenCalledWith(['fr_a', 'fr_b']);
    expect(get(ach.unlockQueue)).toEqual([]);

    // ack failed, Python still says first run: no second toast, the ack is retried
    await ach.checkAchievements();
    expect(get(toasts)).toHaveLength(1);
    expect(fakeApi.ack_achievements).toHaveBeenCalledTimes(2);
    expect(fakeApi.ack_achievements).toHaveBeenNthCalledWith(2, ['fr_a', 'fr_b']);
    expect(get(ach.unlockQueue)).toEqual([]);

    // stored now: nothing left to ride along
    ach.markShown(item('fr_x'));
    expect(fakeApi.ack_achievements).toHaveBeenLastCalledWith(['fr_x']);
  });

  it('after a failed backfill ack, something earned since is a normal unlock', async () => {
    fakeApi.ack_achievements.mockResolvedValue({ ok: false, status: 'error' });
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [item('fr_a'), item('fr_d', null)], newly: ['fr_a'], first_run: true }));
    await ach.checkAchievements();
    fakeApi.get_achievements.mockResolvedValue(
      ok({ items: [item('fr_a'), item('fr_d')], newly: ['fr_a', 'fr_d'], first_run: true }),
    );
    await ach.checkAchievements();
    expect(fakeApi.ack_achievements).toHaveBeenCalledTimes(2);
    expect(fakeApi.ack_achievements).toHaveBeenNthCalledWith(2, ['fr_a']);
    expect(get(ach.unlockQueue).map((a) => a.id)).toEqual(['fr_d']);
    expect(get(toasts)).toHaveLength(1);

    // the card's ack can't end the first run without the backfill
    fakeApi.ack_achievements.mockResolvedValue({ ok: true, status: 'ok' });
    ach.markShown(get(ach.unlockQueue)[0]);
    expect(fakeApi.ack_achievements).toHaveBeenLastCalledWith(['fr_d', 'fr_a']);
    await vi.waitFor(() => expect(fakeApi.ack_achievements).toHaveBeenCalledTimes(3));
    await Promise.resolve();
    ach.markShown(item('fr_y'));
    expect(fakeApi.ack_achievements).toHaveBeenLastCalledWith(['fr_y']);
  });

  it('first run with nothing earned acks an empty list', async () => {
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [item('fr_none', null)], newly: [], first_run: true }));
    await ach.checkAchievements();
    expect(get(toasts)).toEqual([]);
    expect(fakeApi.ack_achievements).toHaveBeenCalledWith([]);
  });

  it('the summary toast link is not an undo', async () => {
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [item('fr_c')], newly: ['fr_c'], first_run: true }));
    await ach.checkAchievements();
    expect(get(toasts)[0].label).toBe('View');
    expect(runUndo()).toBe(false);
    expect(get(toasts)).toHaveLength(1);
  });

  it('queues each new unlock once and acks it only when shown', async () => {
    const data = ok({ items: [item('q_a'), item('q_b'), item('q_c', null)], newly: ['q_a', 'q_b'], first_run: false });
    fakeApi.get_achievements.mockResolvedValue(data);
    await ach.checkAchievements();
    expect(get(ach.unlockQueue).map((a) => a.id)).toEqual(['q_a', 'q_b']);
    expect(fakeApi.ack_achievements).not.toHaveBeenCalled();
    expect(get(ach.achievements)?.items).toHaveLength(3);
    expect(get(toasts)).toEqual([]);

    // still unacked on the next check: not queued twice
    await ach.checkAchievements();
    expect(get(ach.unlockQueue)).toHaveLength(2);

    ach.markShown(get(ach.unlockQueue)[0]);
    expect(fakeApi.ack_achievements).toHaveBeenCalledWith(['q_a']);
    ach.nextUnlock();
    expect(get(ach.unlockQueue).map((a) => a.id)).toEqual(['q_b']);
  });

  it('a thrown ack while showing is caught', async () => {
    // An uncaught rejection here fails the run (vitest reports unhandled errors).
    fakeApi.ack_achievements.mockRejectedValue(new Error('offline'));
    ach.markShown(item('q_z'));
    await new Promise((r) => setTimeout(r, 0));
    expect(fakeApi.ack_achievements).toHaveBeenCalledWith(['q_z']);
  });

  it('drops a waiting card whose achievement is no longer met, and queues it again if re-earned', async () => {
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [item('p_a'), item('p_b')], newly: ['p_a', 'p_b'], first_run: false }));
    await ach.checkAchievements();
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [item('p_a'), item('p_b', null)], newly: ['p_a'], first_run: false }));
    await ach.checkAchievements();
    expect(get(ach.unlockQueue).map((a) => a.id)).toEqual(['p_a']);
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [item('p_a'), item('p_b')], newly: ['p_a', 'p_b'], first_run: false }));
    await ach.checkAchievements();
    expect(get(ach.unlockQueue).map((a) => a.id)).toEqual(['p_a', 'p_b']);
  });

  it('a big batch animates the three rarest and sums up the rest', async () => {
    const tiers = ['bronze', 'gold', 'silver', 'bronze', 'legendary'] as const;
    const items = tiers.map((tier, i) => ({ ...item(`b_${i}`), tier }));
    fakeApi.get_achievements.mockResolvedValue(ok({ items, newly: items.map((a) => a.id), first_run: false }));
    await ach.checkAchievements();
    expect(get(ach.unlockQueue).map((a) => a.tier)).toEqual(['legendary', 'gold', 'silver']);
    expect(get(toasts).map((t) => t.message)).toEqual(['🏆 …and 2 more achievements unlocked']);
    // the toast celebrates the rest now; the three cards ack as they show
    expect(fakeApi.ack_achievements).toHaveBeenCalledTimes(1);
    expect(fakeApi.ack_achievements).toHaveBeenCalledWith(['b_0', 'b_3']);
  });

  it('errors are quiet and keep the last data', async () => {
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [item('e_a')], newly: [], first_run: false }));
    await ach.checkAchievements();
    fakeApi.get_achievements.mockResolvedValue({ ok: false, status: 'error', error: { code: 'internal', message: 'x' } });
    await ach.checkAchievements();
    expect(get(ach.achievements)?.items[0].id).toBe('e_a');
    expect(get(toasts)).toEqual([]);
    expect(get(ach.achievementsError)).toBeTruthy();
  });

  it('a thrown call sets the error, and the next success clears it', async () => {
    fakeApi.get_achievements.mockRejectedValueOnce(new Error('bridge gone'));
    await ach.checkAchievements();
    expect(get(ach.achievementsError)).toBeTruthy();
    expect(get(ach.achievements)).toBeNull();
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [], newly: [], first_run: false }));
    await ach.checkAchievements();
    expect(get(ach.achievementsError)).toBeNull();
  });

  it('coalesces calls made while one is in flight into one rerun', async () => {
    let release!: () => void;
    fakeApi.get_achievements.mockImplementationOnce(
      () => new Promise((r) => (release = () => r(ok({ items: [], newly: [], first_run: false })))),
    );
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [], newly: [], first_run: false }));
    const first = ach.checkAchievements();
    expect(get(ach.achievementsLoading)).toBe(true);
    void ach.checkAchievements();
    void ach.checkAchievements();
    release();
    await first;
    expect(fakeApi.get_achievements).toHaveBeenCalledTimes(2);
    expect(get(ach.achievementsLoading)).toBe(false);
  });
});

describe('startAchievements', () => {
  it('re-checks (debounced) when the month is re-read or target / pay rate change', async () => {
    vi.useFakeTimers();
    fakeApi.get_achievements.mockResolvedValue(ok({ items: [], newly: [], first_run: false }));
    ach.startAchievements();
    ach.startAchievements(); // idempotent
    await vi.advanceTimersByTimeAsync(400);
    expect(fakeApi.get_achievements).toHaveBeenCalledTimes(1);

    fakeStores.month.set({ year: 2026, month: 10, entries: [] });
    fakeStores.month.set({ year: 2026, month: 10, entries: [] });
    await vi.advanceTimersByTimeAsync(400);
    expect(fakeApi.get_achievements).toHaveBeenCalledTimes(2);

    // unrelated settings change: no check
    fakeStores.settings.update((s: any) => ({ ...s, appearance: 'Dark' }));
    await vi.advanceTimersByTimeAsync(400);
    expect(fakeApi.get_achievements).toHaveBeenCalledTimes(2);

    fakeStores.settings.update((s: any) => ({ ...s, ui_prefs: { target_hours: 6 } }));
    await vi.advanceTimersByTimeAsync(400);
    expect(fakeApi.get_achievements).toHaveBeenCalledTimes(3);
  });
});

describe('medalUrl', () => {
  it('uses the hidden medal until a hidden achievement is unlocked', () => {
    const a = { ...item('night_owl', null), tier: 'silver' as const, hidden: true };
    expect(ach.medalUrl(a)).toContain('hidden_silver');
    expect(ach.medalUrl({ ...a, met_on: '2026-10-01' })).toContain('night_owl');
    expect(ach.medalUrl(item('first_shift'))).toContain('first_shift');
  });
});

