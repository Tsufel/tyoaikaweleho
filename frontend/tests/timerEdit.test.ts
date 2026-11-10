import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { TimerState } from '../src/lib/api/types';

// TimerView's running-shift editors (§6.3a): STOP's right-click menu, the start time and the job.
const spies = vi.hoisted(() => {
  // jsdom has neither; svelte/motion reads matchMedia at import time
  const mq = { matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} };
  window.matchMedia ??= (() => mq) as unknown as typeof window.matchMedia;
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  // svelte transitions use the Web Animations API; finish them at once
  Element.prototype.animate ??= function () {
    const a = { onfinish: null as null | (() => void), cancel() {}, finish() {}, currentTime: 0, effect: null };
    queueMicrotask(() => a.onfinish?.());
    return a as unknown as Animation;
  };
  return { stopShiftAt: vi.fn(), adjustShift: vi.fn(), stopShift: vi.fn() };
});

vi.mock('../src/lib/api/bridge', () => ({ api: {}, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/views/timer/timerActions', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/views/timer/timerActions')>()),
  stopShiftAt: spies.stopShiftAt,
  adjustShift: spies.adjustShift,
  stopShift: spies.stopShift,
}));

const { setTimer, IDLE_TIMER } = await import('../src/lib/stores/timer');
const { default: TimerView } = await import('../src/views/timer/TimerView.svelte');

const running: TimerState = {
  ...IDLE_TIMER,
  running: true,
  start_iso: '2026-10-29T09:00:00',
  start_epoch_ms: new Date(2026, 9, 29, 9, 0).getTime(),
  job_shift: 'Support',
  default_job_shift: 'Support',
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  setTimer(running);
});
afterEach(() => {
  cleanup();
  setTimer(IDLE_TIMER);
});

async function submit(value: string) {
  const input = (await screen.findByRole('dialog')).querySelector('input')!;
  await fireEvent.input(input, { target: { value } });
  await fireEvent.submit(input.closest('form')!);
  await tick();
}

const stopBar = () => screen.getByRole('button', { name: /^STOP/ });

/** Right-click on STOP, then pick from its menu. */
async function stopMenu(item?: string) {
  await fireEvent.contextMenu(stopBar(), { clientX: 120, clientY: 300 });
  await tick();
  if (item) {
    await fireEvent.click(screen.getByRole('menuitem', { name: new RegExp(`^${item}`) }));
    await tick();
  }
}

/** The start / job line is folded behind ⋯ until opened. */
async function showDetails() {
  await fireEvent.click(screen.getByRole('button', { name: 'Show details' }));
  await tick();
}

describe('details fold (⋯)', () => {
  it('hides the start / job line until ⋯ is clicked, and remembers the choice', async () => {
    render(TimerView);
    expect(screen.queryByRole('button', { name: /^Started 09:00/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'Show details' }).getAttribute('aria-expanded')).toBe('false');
    await showDetails();
    expect(screen.getByRole('button', { name: /^Started 09:00/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Support' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Hide details' }).getAttribute('aria-expanded')).toBe('true');
    expect(localStorage.getItem('weleho.timerDetails')).toBe('1');

    cleanup();
    render(TimerView);
    expect(screen.getByRole('button', { name: /^Started 09:00/ })).toBeTruthy();
    await fireEvent.click(screen.getByRole('button', { name: 'Hide details' }));
    await tick();
    expect(screen.queryByRole('button', { name: /^Started 09:00/ })).toBeNull();
    expect(localStorage.getItem('weleho.timerDetails')).toBeNull();
  });

  it('folding the line away closes an open start editor', async () => {
    render(TimerView);
    await showDetails();
    await fireEvent.click(screen.getByRole('button', { name: /^Started 09:00/ }));
    expect(await screen.findByRole('dialog')).toBeTruthy();
    await fireEvent.click(screen.getByRole('button', { name: 'Hide details' }));
    await tick();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(spies.adjustShift).not.toHaveBeenCalled();
  });

  it('the STOP menu works with the details folded', async () => {
    render(TimerView);
    await stopMenu('Stop at an earlier time');
    expect(await screen.findByRole('dialog', { name: 'Stop at an earlier time' })).toBeTruthy();
  });
});

describe('STOP bar', () => {
  it('is the only control: no chevron beside it', () => {
    render(TimerView);
    expect(stopBar().parentElement!.querySelectorAll('button')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Stop at an earlier time' })).toBeNull();
  });

  it('right-click opens the stop menu instead of stopping', async () => {
    render(TimerView);
    await stopMenu();
    const items = screen.getAllByRole('menuitem').map((b) => b.textContent?.trim());
    expect(items).toEqual(['Stop now F5', 'Stop at an earlier time…', 'Change the start time…', 'Change the job…']);
    expect(spies.stopShift).not.toHaveBeenCalled();
  });

  it('Shift+F10 and the menu key open it too', async () => {
    render(TimerView);
    await fireEvent.keyDown(stopBar(), { key: 'F10', shiftKey: true });
    await tick();
    expect(screen.getByRole('menu', { name: 'Stop options' })).toBeTruthy();
    await fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' });
    await tick();
    expect(screen.queryByRole('menu')).toBeNull();
    await fireEvent.keyDown(stopBar(), { key: 'ContextMenu' });
    await tick();
    expect(screen.getByRole('menu')).toBeTruthy();
  });

  it('Stop now stops, as a click on the bar does', async () => {
    render(TimerView);
    await stopMenu('Stop now');
    expect(spies.stopShift).toHaveBeenCalledWith('button');
    expect(screen.queryByRole('menu')).toBeNull();
    await fireEvent.click(stopBar());
    expect(spies.stopShift).toHaveBeenCalledTimes(2);
  });

  it('closes when a flow starts (F5 asking "Stop shift?"), focus back on STOP', async () => {
    const { busy } = await import('../src/views/timer/timerActions');
    render(TimerView);
    await fireEvent.keyDown(stopBar(), { key: 'F10', shiftKey: true });
    await tick();
    await vi.waitFor(() => expect(screen.getByRole('menu').contains(document.activeElement)).toBe(true));
    busy.set(true);
    try {
      await vi.waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
      expect(document.querySelector('.menu-point')).toBeNull();
    } finally {
      busy.set(false);
    }
    // STOP is disabled while busy; focus lands on it when the flow ends
    await vi.waitFor(() => expect(document.activeElement).toBe(stopBar()));
  });

  it('a second right-click opens a fresh menu at the new point, focused', async () => {
    render(TimerView);
    await stopMenu();
    expect(document.querySelector<HTMLElement>('.menu-point')!.style.left).toBe('120px');
    // the pointerdown of the next right-click closes the first menu; its contextmenu reopens at once
    await fireEvent.pointerDown(stopBar());
    await fireEvent.contextMenu(stopBar(), { clientX: 400, clientY: 310 });
    await tick();
    expect(document.querySelector<HTMLElement>('.menu-point')!.style.left).toBe('400px');
    await vi.waitFor(() => expect(screen.getByRole('menu').contains(document.activeElement)).toBe(true));
    expect(screen.getAllByRole('menu')).toHaveLength(1);
  });

  it('the start and job editors open from the menu with the details folded', async () => {
    render(TimerView);
    await stopMenu('Change the start time');
    await submit('08:45');
    expect(spies.adjustShift).toHaveBeenCalledWith('08:45', null);
    await stopMenu('Change the job');
    await submit('Kitchen');
    expect(spies.adjustShift).toHaveBeenCalledWith(null, 'Kitchen');
  });
});

describe('running shift editors', () => {
  it('Stop at an earlier time saves the shift at the typed end time', async () => {
    render(TimerView);
    await stopMenu('Stop at an earlier time');
    await submit('1630');
    expect(spies.stopShiftAt).toHaveBeenCalledWith('16:30');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('keeps the editor open on a time it cannot read', async () => {
    render(TimerView);
    await stopMenu('Stop at an earlier time');
    await submit('half four');
    expect(spies.stopShiftAt).not.toHaveBeenCalled();
    expect(screen.getByText(/Use HH:MM/)).toBeTruthy();
  });

  it('the start time in the status line moves the start', async () => {
    render(TimerView);
    await showDetails();
    await fireEvent.click(screen.getByRole('button', { name: /^Started 09:00/ }));
    await submit('08:45');
    expect(spies.adjustShift).toHaveBeenCalledWith('08:45', null);
  });

  it('the job in the status line changes the job, and an unchanged one is a no-op', async () => {
    render(TimerView);
    await showDetails();
    await fireEvent.click(screen.getByRole('button', { name: 'Support' }));
    await submit('Support');
    expect(spies.adjustShift).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button', { name: 'Support' }));
    await submit(' Kitchen ');
    expect(spies.adjustShift).toHaveBeenCalledWith(null, 'Kitchen');
  });
});
