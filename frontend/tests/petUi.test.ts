import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Settings } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({ get_pet_stats: vi.fn(), save_ui_prefs: vi.fn() }));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: () => true }));
vi.mock('../src/lib/stores/entries', async () => {
  const { writable } = await import('svelte/store');
  return { month: writable(null) };
});

const { DEFAULT_SETTINGS, applySettings, settings } = await import('../src/lib/stores/settings');
const { petStats } = await import('../src/lib/stores/pet');
const { dialogs } = await import('../src/lib/stores/confirm');
const { IDLE_TIMER, setTimer } = await import('../src/lib/stores/timer');
const {
  BAZOOKA_MS,
  commitPetName,
  newlyUnlockedSkins,
  petFlyby,
  petSpot,
  petView,
  PET_MIN_W,
  putAwayBazooka,
  resetSkinUnlocks,
  rollBazooka,
} = await import('../src/views/pet/petState');
const { FRIDAY_LINES, TIRED_LINES } = await import('../src/views/pet/petLogic');
const { burst, savedEntry } = await import('../src/views/timer/timerActions');
const PetCompanion = (await import('../src/views/pet/PetCompanion.svelte')).default;
const PetFlyby = (await import('../src/views/pet/PetFlyby.svelte')).default;
const PetSheet = (await import('../src/views/pet/PetSheet.svelte')).default;
const PetHint = (await import('../src/views/pet/PetHint.svelte')).default;
const PetHintHost = (await import('./fixtures/PetHintHost.svelte')).default;
const { route } = await import('../src/lib/stores/app');
const { clearToasts, toasts } = await import('../src/lib/stores/toasts');

// Reduced motion: no loops or transitions, so jsdom needs no Web Animations.
function useSettings(prefs: Partial<Settings['ui_prefs']>) {
  applySettings({ ...DEFAULT_SETTINGS, ui_prefs: { ...DEFAULT_SETTINGS.ui_prefs, reduce_effects: true, ...prefs } });
}

beforeEach(() => {
  useSettings({ pet: 'familiar' });
  petStats.set({ lifetime_minutes: 600, days: {} });
  fakeApi.get_pet_stats.mockReset().mockResolvedValue({ ok: true, lifetime_minutes: 600, days: {} });
  fakeApi.save_ui_prefs.mockReset().mockImplementation(async (prefs: Partial<Settings['ui_prefs']>) => {
    const s = get(settings);
    return { ok: true, status: 'ok', settings: { ...s, ui_prefs: { ...s.ui_prefs, ...prefs } } };
  });
});
afterEach(() => {
  cleanup();
  putAwayBazooka();
  resetSkinUnlocks();
  clearToasts();
  for (const d of get(dialogs)) if (d.type === 'sheet') d.resolve(undefined);
  document.body.innerHTML = '';
});

describe('petSpot', () => {
  const box = (left: number, top: number, w: number, h: number) => ({ left, top, right: left + w, bottom: top + h });
  const familiar = { w: 142, h: 122 };

  it('takes the corner under the controls at 1× when there is room', () => {
    const spot = petSpot(box(0, 0, 500, 700), box(90, 60, 320, 320), box(20, 430, 460, 100), familiar);
    expect(spot).toEqual({ x: 500 - 16 - 142, y: 700 - 16 - 122, w: 142 });
  });

  it('stands beside the ring when the card is short', () => {
    const spot = petSpot(box(0, 0, 680, 470), box(235, 65, 230, 230), box(20, 340, 640, 104), familiar);
    expect(spot?.w).toBe(142);
    expect(spot!.x).toBeGreaterThanOrEqual(465 + 8);
    expect(spot!.x + 142).toBeLessThanOrEqual(680 - 16);
    expect(spot!.y + 122).toBeCloseTo(295);
  });

  it('shrinks to the bigger spot, and hides below the minimum', () => {
    const tight = petSpot(box(0, 0, 420, 520), box(50, 40, 320, 320), box(20, 370, 380, 60), familiar);
    expect(tight!.w).toBeLessThan(142);
    expect(tight!.w).toBeGreaterThanOrEqual(PET_MIN_W);
    expect(petSpot(box(0, 0, 340, 440), box(10, 10, 320, 320), box(10, 340, 320, 90), familiar)).toBeNull();
  });
});

describe('PetCompanion', () => {
  it('places itself in layout px under the UI zoom', async () => {
    const { applyZoom } = await import('../src/lib/zoom');
    globalThis.ResizeObserver ??= class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
    // visual px at 150 %: the 1x layout of the first petSpot case, scaled up
    const el = (l: number, t: number, w: number, h: number) => {
      const e = document.createElement('div');
      e.getBoundingClientRect = () => new DOMRect(l * 1.5, t * 1.5, w * 1.5, h * 1.5);
      return e;
    };
    const card = el(0, 0, 500, 700);
    applyZoom(150, document.createElement('div'));
    try {
      render(PetCompanion, { card, ring: el(90, 60, 320, 320), controls: el(20, 430, 460, 100) });
      await tick();
      const pet = document.querySelector<HTMLElement>('.pet')!;
      expect(pet.style.left).toBe(`${500 - 16 - 142}px`);
      expect(pet.style.top).toBe(`${700 - 16 - 122}px`);
      expect(pet.style.width).toBe('142px');
    } finally {
      applyZoom(100, document.createElement('div'));
    }
  });

  const body = () => screen.getByRole('button', { hidden: true });
  const sheets = () => get(dialogs).filter((d) => d.type === 'sheet');

  it('names its pose and energy', async () => {
    render(PetCompanion, {});
    await tick();
    expect(body().getAttribute('aria-label')).toMatch(/^Tähti, (awake|asleep|flying|drowsy)[^.]*, energy \d+%\. Open pet$/);
    useSettings({ pet: 'wizard', pet_name: 'Merlin' });
    await tick();
    expect(body().getAttribute('aria-label')).toMatch(/^Merlin, /);
  });

  it('a mouse click pets it; the keyboard and right-click open the sheet', async () => {
    render(PetCompanion, {});
    await fireEvent.click(body(), { detail: 1 });
    expect(document.querySelectorAll('.heart')).toHaveLength(1);
    expect(sheets()).toHaveLength(0);

    await fireEvent.click(body(), { detail: 0 });
    await vi.waitFor(() => expect(sheets()).toHaveLength(1));
    // a second open while one is showing is ignored
    await fireEvent.contextMenu(body());
    await tick();
    expect(sheets()).toHaveLength(1);

    // once it closes, it opens again
    sheets()[0].resolve(undefined);
    await new Promise((r) => setTimeout(r));
    await fireEvent.contextMenu(body());
    await vi.waitFor(() => expect(sheets()).toHaveLength(1));
  });

  it('a right-button release opens the sheet once, even without a contextmenu', async () => {
    render(PetCompanion, {});
    await fireEvent.pointerUp(body(), { button: 2 });
    await vi.waitFor(() => expect(sheets()).toHaveLength(1));
    // the contextmenu that usually follows doesn't open a second one
    await fireEvent.contextMenu(body());
    await new Promise((r) => setTimeout(r));
    expect(sheets()).toHaveLength(1);
    expect(document.querySelectorAll('.heart')).toHaveLength(0);
  });

  it('after a long press, Enter still opens the sheet', async () => {
    vi.useFakeTimers();
    try {
      render(PetCompanion, {});
      await fireEvent.pointerDown(body(), { button: 0, clientX: 5, clientY: 5 });
      await vi.advanceTimersByTimeAsync(600);
    } finally {
      vi.useRealTimers();
    }
    await vi.waitFor(() => expect(sheets()).toHaveLength(1));
    // the pointer was released off the pet, so no click came to eat
    sheets()[0].resolve(undefined);
    await new Promise((r) => setTimeout(r));
    await fireEvent.click(body(), { detail: 0 });
    await vi.waitFor(() => expect(sheets()).toHaveLength(1));
  });

  it('keeps at most four hearts', async () => {
    render(PetCompanion, {});
    for (let i = 0; i < 6; i++) await fireEvent.click(body(), { detail: 1 });
    expect(document.querySelectorAll('.heart')).toHaveLength(4);
  });

  describe('when tired', () => {
    const bubble = () => document.querySelector('.bubble');
    // 7 of the 8 target hours in: past TIRED_AT
    const late = () => setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 7 * 3600_000 });
    afterEach(() => {
      vi.useRealTimers();
      setTimer(IDLE_TIMER);
    });

    it('sighs a line a few seconds in, then again every so often', async () => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
      late();
      render(PetCompanion, {});
      await tick();
      expect(bubble()).toBeNull();
      await vi.advanceTimersByTimeAsync(4000);
      expect(TIRED_LINES).toContain(bubble()?.textContent);
      await vi.advanceTimersByTimeAsync(6000);
      expect(bubble()).toBeNull();
      // the next one comes 10 min after the first (at 604 s), shown for 6 s
      await vi.advanceTimersByTimeAsync(10 * 60_000 - 3000);
      expect(bubble()).not.toBeNull();
    });

    it('sighs when petted, and hushes once the shift ends', async () => {
      late();
      render(PetCompanion, {});
      await tick();
      await fireEvent.click(body(), { detail: 1 });
      expect(bubble()).not.toBeNull();
      setTimer(IDLE_TIMER);
      await tick();
      expect(bubble()).toBeNull();
    });

    it('stays quiet early in a shift', async () => {
      setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 3600_000 });
      render(PetCompanion, {});
      await tick();
      await fireEvent.click(body(), { detail: 1 });
      expect(bubble()).toBeNull();
    });

    it('steps out during the fly-by', async () => {
      late();
      render(PetCompanion, {});
      await tick();
      await fireEvent.click(body(), { detail: 1 });
      petFlyby.set({ id: 1, line: 'Jo oli aikakin' });
      await tick();
      expect(document.querySelector('.pet')!.classList.contains('away')).toBe(true);
      expect(bubble()).toBeNull();
      petFlyby.set(null);
    });
  });
});

describe('PetFlyby', () => {
  const FRIDAY = new Date(2026, 9, 30, 16, 5);
  const THURSDAY = new Date(2026, 9, 29, 16, 5);
  const save = (date: string) => {
    savedEntry.set({ date } as never);
    burst.update((n) => n + 1);
  };
  afterEach(() => {
    vi.useRealTimers();
    petFlyby.set(null);
  });

  it('flies by with a Friday line when a shift is saved on a Friday', async () => {
    vi.useFakeTimers({ now: FRIDAY, toFake: ['setTimeout', 'clearTimeout', 'Date'] });
    render(PetFlyby, {});
    await tick();
    expect(get(petFlyby)).toBeNull();
    save('2026-10-30');
    await tick();
    const line = get(petFlyby)?.line;
    expect(FRIDAY_LINES).toContain(line);
    // announced through the always-mounted live region; the drawing is hidden
    expect(screen.getByRole('status').textContent).toBe(line);
    expect(document.querySelector('.flyby')!.getAttribute('aria-hidden')).toBe('true');
    // reduced motion: a still visit
    await vi.advanceTimersByTimeAsync(4500);
    expect(get(petFlyby)).toBeNull();
    expect(document.querySelector('.flyby')).toBeNull();
    expect(screen.getByRole('status').textContent).toBe('');
  });

  it('counts a Friday shift that ran past midnight', async () => {
    vi.useFakeTimers({ now: new Date(2026, 9, 31, 1), toFake: ['setTimeout', 'clearTimeout', 'Date'] });
    render(PetFlyby, {});
    save('2026-10-30');
    await tick();
    expect(get(petFlyby)).not.toBeNull();
  });

  it('stays home on other days and when the pet is off', async () => {
    vi.useFakeTimers({ now: THURSDAY, toFake: ['setTimeout', 'clearTimeout', 'Date'] });
    render(PetFlyby, {});
    save('2026-10-29');
    await tick();
    expect(get(petFlyby)).toBeNull();

    vi.setSystemTime(FRIDAY);
    useSettings({ pet: 'off' });
    save('2026-10-30');
    await tick();
    expect(get(petFlyby)).toBeNull();
  });

  it('does not fly for a shift saved before it mounted', async () => {
    vi.useFakeTimers({ now: FRIDAY, toFake: ['setTimeout', 'clearTimeout', 'Date'] });
    save('2026-10-30');
    render(PetFlyby, {});
    await tick();
    expect(get(petFlyby)).toBeNull();
  });
});

describe('PetSheet', () => {
  it('shows level and energy, and leaves naming to Settings', async () => {
    route.set('main');
    const onclose = vi.fn();
    render(PetSheet, { onclose });
    await vi.waitFor(() => expect(document.body.textContent).toContain('Level 2'));
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(document.body.textContent).toContain('Settings ▸ Effects ▸ Pet');
    await fireEvent.click(screen.getByRole('button', { name: 'Pet settings' }));
    expect(onclose).toHaveBeenCalled();
    await vi.waitFor(() => expect(get(route)).toBe('settings'));
  });

  const look = (name: string) => screen.getByRole('button', { name: new RegExp(`^${name}`) });

  it('shows the looks, locked ones with the level that unlocks them', async () => {
    render(PetSheet, { onclose: vi.fn() });
    await vi.waitFor(() => expect(look('Classic')).toBeTruthy());
    expect(look('Classic').getAttribute('aria-pressed')).toBe('true');
    // locked looks stay focusable, so keyboard users can read what they are
    expect(look('Cosmic').getAttribute('aria-disabled')).toBe('true');
    expect(look('Cosmic').textContent!.replace(/\s+/g, ' ').trim()).toBe('Cosmic Unlocks at Level 5');
    await fireEvent.click(look('Cosmic'));
    expect(fakeApi.save_ui_prefs).not.toHaveBeenCalled();
    // the after-shift bazooka is a surprise, not a look
    expect(screen.queryByRole('button', { name: /Bazooka/ })).toBeNull();
  });

  it('wears an unlocked look', async () => {
    // Lv 12: classic, cosmic and neon open
    fakeApi.get_pet_stats.mockResolvedValue({ ok: true, lifetime_minutes: 300 * 60, days: {} });
    petStats.set({ lifetime_minutes: 300 * 60, days: {} });
    render(PetSheet, { onclose: vi.fn() });
    await vi.waitFor(() => expect(look('Neon').getAttribute('aria-disabled')).toBe('false'));
    expect(look('Gilded').getAttribute('aria-disabled')).toBe('true');
    await fireEvent.click(look('Neon'));
    expect(fakeApi.save_ui_prefs).toHaveBeenCalledWith({ pet_skin: 'neon' });
    await vi.waitFor(() => expect(look('Neon').getAttribute('aria-pressed')).toBe('true'));
    expect(look('Classic').getAttribute('aria-pressed')).toBe('false');
    expect(document.querySelector('.hero img')!.getAttribute('src')).toMatch(/familiar_(idle|sleep)/);
  });

  it('picking Classic saves it even while a locked choice already draws classic', async () => {
    // Neon chosen, then entries deleted: level 2, drawn classic
    useSettings({ pet: 'familiar', pet_skin: 'neon' });
    render(PetSheet, { onclose: vi.fn() });
    await vi.waitFor(() => expect(look('Classic').getAttribute('aria-pressed')).toBe('true'));
    await fireEvent.click(look('Classic'));
    expect(fakeApi.save_ui_prefs).toHaveBeenCalledWith({ pet_skin: 'classic' });
  });
});

describe('petView', () => {
  afterEach(() => setTimer(IDLE_TIMER));

  it("keeps a stopped shift's hours until the stats are re-read", () => {
    const before = { lifetime_minutes: 600, days: {} };
    petStats.set(before);
    setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 60 * 60_000 });
    expect(get(petView).level!.hours).toBeCloseTo(11, 1);

    setTimer(IDLE_TIMER);
    expect(get(petView).level!.hours).toBeCloseTo(11, 1);
    expect(get(petView).energy!.hours).toBeCloseTo(1, 1);

    // saved: the new numbers take over
    petStats.set({ lifetime_minutes: 660, days: {} });
    expect(get(petView).level!.hours).toBe(11);
    // discarded: a re-read with the old numbers drops it
    petStats.set({ ...before });
    expect(get(petView).level!.hours).toBe(10);
  });
});

describe('looks', () => {
  it('draws a chosen look as classic until its level is reached', () => {
    useSettings({ pet: 'wizard', pet_skin: 'gilded' });
    petStats.set({ lifetime_minutes: 600, days: {} });
    expect(get(petView).skin).toBe('classic');
    petStats.set({ lifetime_minutes: 900 * 60, days: {} });
    expect(get(petView).skin).toBe('gilded');
    // still loading: the last level known decides
    petStats.set(null);
    expect(get(petView).skin).toBe('gilded');
    petStats.set({ lifetime_minutes: 600, days: {} });
    expect(get(petView).skin).toBe('classic');
    petStats.set(null);
    expect(get(petView).skin).toBe('classic');
  });

  it('remembers the level for the next start, so a locked look never flashes', () => {
    useSettings({ pet: 'wizard', pet_skin: 'gilded' });
    petStats.set({ lifetime_minutes: 600, days: {} });
    expect(get(petView).skin).toBe('classic');
    expect(localStorage.getItem('weleho.petLevel')).toBe('2');
    // a first run (nothing remembered) keeps the choice while loading
    resetSkinUnlocks();
    petStats.set(null);
    expect(get(petView).skin).toBe('gilded');
  });

  it('reports a looks unlock once, when the level climbs past one', () => {
    expect(newlyUnlockedSkins(null)).toEqual([]);
    // the first level seen (an app start) is never news
    expect(newlyUnlockedSkins(4)).toEqual([]);
    expect(newlyUnlockedSkins(4)).toEqual([]);
    expect(newlyUnlockedSkins(5).map((s) => s.id)).toEqual(['cosmic']);
    expect(newlyUnlockedSkins(5)).toEqual([]);
    // dropping (entries deleted) and climbing back isn't news again
    expect(newlyUnlockedSkins(3)).toEqual([]);
    expect(newlyUnlockedSkins(5)).toEqual([]);
    expect(newlyUnlockedSkins(21).map((s) => s.id)).toEqual(['neon', 'gilded']);
  });

  it('the companion offers to wear a look its level just unlocked', async () => {
    render(PetCompanion, {});
    await tick();
    petStats.set({ lifetime_minutes: 80 * 60, days: {} });
    await tick();
    const t = get(toasts).find((x) => x.message.includes('Cosmic'));
    expect(t?.message).toBe('Tähti unlocked the Cosmic look at level 5');
    expect(t?.label).toBe('Wear it');
    await t!.action!();
    expect(fakeApi.save_ui_prefs).toHaveBeenCalledWith({ pet_skin: 'cosmic' });
  });

  it('a running shift never announces a look, only saved hours do', async () => {
    vi.useFakeTimers({ now: new Date(2026, 9, 28, 14, 0), toFake: ['Date'] });
    try {
      petStats.set({ lifetime_minutes: 79 * 60, days: {} });
      render(PetCompanion, {});
      await tick();
      // two hours into a shift: level 5 on the sheet, but the shift may be discarded
      setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 2 * 3600_000 });
      await tick();
      expect(get(petView).level?.level).toBe(5);
      expect(get(toasts).some((x) => x.message.includes('Cosmic'))).toBe(false);
      // saved: now it counts
      setTimer(IDLE_TIMER);
      petStats.set({ lifetime_minutes: 81 * 60, days: {} });
      await tick();
      expect(get(toasts).some((x) => x.message.includes('Cosmic'))).toBe(true);
    } finally {
      vi.useRealTimers();
      setTimer(IDLE_TIMER);
    }
  });
});

describe('after-shift bazooka', () => {
  // a Wednesday afternoon with a shift logged today: awake
  const NOON = new Date(2026, 9, 28, 14, 0);
  const awake = { lifetime_minutes: 600, days: { '2026-10-28': 480 } };
  beforeEach(() => {
    vi.useFakeTimers({ now: NOON, toFake: ['setTimeout', 'clearTimeout', 'Date'] });
    petStats.set(awake);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    setTimer(IDLE_TIMER);
  });

  it('comes out now and then, for a minute', async () => {
    expect(rollBazooka(0.9)).toBe(false);
    expect(get(petView).bazooka).toBe(false);
    expect(rollBazooka(0.1)).toBe(true);
    expect(get(petView)).toMatchObject({ pose: 'idle', bazooka: true });
    await vi.advanceTimersByTimeAsync(BAZOOKA_MS - 1000);
    expect(get(petView).bazooka).toBe(true);
    await vi.advanceTimersByTimeAsync(1000);
    expect(get(petView).bazooka).toBe(false);
  });

  it('is only held while awake', () => {
    rollBazooka(0);
    setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 60_000 });
    expect(get(petView)).toMatchObject({ pose: 'fly', bazooka: false });
  });

  it('a saved shift may bring it out on the companion, and starting one puts it away', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0);
    render(PetCompanion, {});
    await tick();
    const body = screen.getByRole('button', { hidden: true });
    expect(body.getAttribute('aria-label')).not.toContain('bazooka');
    burst.update((n) => n + 1);
    await tick();
    expect(body.getAttribute('aria-label')).toMatch(/^Tähti, awake, holding a bazooka, energy/);
    expect(body.querySelector('img')!.getAttribute('src')).toContain('familiar_idle_bazooka');

    setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 60_000 });
    await tick();
    setTimer(IDLE_TIMER);
    await tick();
    expect(body.getAttribute('aria-label')).not.toContain('bazooka');
  });

  it('stays put away most of the time', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    render(PetCompanion, {});
    await tick();
    burst.update((n) => n + 1);
    await tick();
    expect(get(petView).bazooka).toBe(false);
  });
});

describe('commitPetName', () => {
  it('skips the save when nothing changed', async () => {
    useSettings({ pet: 'familiar', pet_name: 'Tähti' });
    expect(await commitPetName(' Tähti ')).toBe('Tähti');
    expect(fakeApi.save_ui_prefs).not.toHaveBeenCalled();
  });

  it('keeps the old name when the save fails', async () => {
    useSettings({ pet: 'familiar', pet_name: 'Old' });
    fakeApi.save_ui_prefs.mockResolvedValue({ ok: false, status: 'error', error: { message: 'nope' } });
    expect(await commitPetName('New')).toBe('Old');
  });
});

describe('PetHint', () => {
  beforeEach(() => {
    useSettings({ pet: 'off' });
    clearToasts();
    route.set('main');
  });

  it('turns the picked pet on, marks the offer answered and says where the setting lives', async () => {
    render(PetHint, {});
    await fireEvent.click(screen.getByRole('button', { name: 'Wizard' }));
    expect(fakeApi.save_ui_prefs).toHaveBeenCalledWith({ pet: 'wizard', pet_hint_seen: true });
    expect(get(settings).ui_prefs).toMatchObject({ pet: 'wizard', pet_hint_seen: true });
    const [t] = get(toasts);
    expect(t.message).toMatch(/^Say hi to Weleho!.*Settings ▸ Effects ▸ Pet$/);
  });

  it('No thanks only marks it answered, and the toast opens Settings', async () => {
    render(PetHint, {});
    await fireEvent.click(screen.getByRole('button', { name: 'No thanks' }));
    expect(fakeApi.save_ui_prefs).toHaveBeenCalledWith({ pet_hint_seen: true });
    expect(get(settings).ui_prefs).toMatchObject({ pet: 'off', pet_hint_seen: true });
    const [t] = get(toasts);
    expect(t.message).toMatch(/Settings ▸ Effects ▸ Pet$/);
    expect(t.label).toBe('Open Settings');
    await t.action!();
    expect(get(route)).toBe('settings');
  });

  it('keeps keyboard focus in the card once the strip is gone', async () => {
    render(PetHintHost, {});
    const no = screen.getByRole('button', { name: 'No thanks' });
    no.focus();
    await fireEvent.click(no);
    await tick();
    await tick();
    expect(screen.queryByRole('group', { name: 'Want a work pet?' })).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'START NOW' }));
  });

  it('leaves focus alone after a mouse click', async () => {
    render(PetHintHost, {});
    const no = screen.getByRole('button', { name: 'No thanks' });
    no.focus();
    await fireEvent.click(no, { detail: 1 });
    await tick();
    await tick();
    expect(screen.queryByRole('group', { name: 'Want a work pet?' })).toBeNull();
    expect(document.activeElement).toBe(document.body);
  });

  it("says when the card has no room to show the pet it just turned on", async () => {
    // the host has no PetCompanion, so the pet never gets a spot
    render(PetHintHost, {});
    await fireEvent.click(screen.getByRole('button', { name: 'Familiar' }), { detail: 1 });
    await vi.waitFor(() => expect(get(toasts)).toHaveLength(1));
    expect(get(toasts)[0].message).toMatch(/^Tähti is ready but needs more room/);
  });

  it('a click or right-click on the preview picture says, once, how to get the pet', async () => {
    render(PetHint, {});
    const art = document.querySelector('.pet-hint .art')!;
    await fireEvent.contextMenu(art);
    await fireEvent.click(art);
    expect(get(toasts).map((t) => t.message)).toEqual([
      'Pick Familiar or Wizard to get your pet. Then click it to pet it, or right-click it for its details',
    ]);
    expect(fakeApi.save_ui_prefs).not.toHaveBeenCalled();
  });

  it('stays unanswered when the save fails', async () => {
    fakeApi.save_ui_prefs.mockResolvedValue({ ok: false, status: 'error', error: { message: 'nope' } });
    render(PetHint, {});
    await fireEvent.click(screen.getByRole('button', { name: 'Familiar' }));
    await tick();
    expect(get(settings).ui_prefs).toMatchObject({ pet: 'off', pet_hint_seen: false });
    expect(get(toasts).map((t) => t.tone)).toEqual(['error']);
  });
});

describe('pet sheet mood and streak', () => {
  const mood = () => document.querySelector('.mood')?.textContent?.replace(/\s+/g, ' ').trim();
  afterEach(() => {
    vi.useRealTimers();
    setTimer(IDLE_TIMER);
  });

  it('says the target is almost done at 80%, and past it only in overtime', async () => {
    // 6.4 of 8 h: drowsy (past TIRED_AT) but not past the target
    setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 6.4 * 3600_000 });
    render(PetSheet, { onclose: vi.fn() });
    await vi.waitFor(() => expect(mood()).toBe("Tähti is getting sleepy: today's target is almost done."));
    setTimer({ ...IDLE_TIMER, running: true, start_epoch_ms: Date.now() - 8.5 * 3600_000 });
    await vi.waitFor(() => expect(mood()).toBe("Tähti is getting sleepy: you're past today's target."));
  });

  it('shows the workday streak from two days, today not breaking it', async () => {
    // Wednesday, nothing logged yet today
    vi.useFakeTimers({ now: new Date(2026, 9, 28, 14, 0), toFake: ['Date'] });
    const days = { '2026-10-23': 480, '2026-10-26': 480, '2026-10-27': 480 };
    fakeApi.get_pet_stats.mockResolvedValue({ ok: true, lifetime_minutes: 1440, days });
    petStats.set({ lifetime_minutes: 1440, days });
    render(PetSheet, { onclose: vi.fn() });
    await vi.waitFor(() =>
      expect(document.querySelector('.streak')?.textContent).toBe('🔥 3 workdays at target in a row'),
    );
  });

  it('has no streak chip below two', async () => {
    vi.useFakeTimers({ now: new Date(2026, 9, 28, 14, 0), toFake: ['Date'] });
    const days = { '2026-10-27': 480 };
    fakeApi.get_pet_stats.mockResolvedValue({ ok: true, lifetime_minutes: 480, days });
    petStats.set({ lifetime_minutes: 480, days });
    render(PetSheet, { onclose: vi.fn() });
    await vi.waitFor(() => expect(document.body.textContent).toContain('Energy'));
    expect(document.querySelector('.streak')).toBeNull();
  });
});

describe('pet chatter', () => {
  const body = () => screen.getByRole('button', { hidden: true });
  const bubble = () => document.querySelector('.bubble');
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('an awake pet greets you now and then when petted', async () => {
    // a Wednesday morning with a shift logged today: awake
    vi.useFakeTimers({ now: new Date(2026, 9, 28, 8, 0), toFake: ['Date'] });
    petStats.set({ lifetime_minutes: 600, days: { '2026-10-28': 60 } });
    render(PetCompanion, {});
    await tick();
    const roll = vi.spyOn(Math, 'random').mockReturnValue(0.9);
    await fireEvent.click(body(), { detail: 1 });
    expect(bubble()).toBeNull();
    roll.mockReturnValue(0);
    await fireEvent.click(body(), { detail: 1 });
    expect(['Huomenta!', 'Moro!']).toContain(bubble()?.textContent);
  });

  it('protests when tickled', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.9); // no greetings in between
    render(PetCompanion, {});
    await tick();
    for (let i = 0; i < 7; i++) await fireEvent.click(body(), { detail: 1 });
    expect(bubble()).toBeNull();
    await fireEvent.click(body(), { detail: 1 });
    expect(bubble()?.textContent).toBe('Älä kutita!');
  });
});
