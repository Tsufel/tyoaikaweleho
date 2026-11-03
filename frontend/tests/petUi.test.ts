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
const { commitPetName, petFlyby, petSpot, petView, PET_MIN_W } = await import('../src/views/pet/petState');
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
