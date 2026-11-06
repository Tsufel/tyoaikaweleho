import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { TimerState } from '../src/lib/api/types';

// TimerView's running-shift editors (§6.3a): STOP ▾, the start time and the job.
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
  return { stopShiftAt: vi.fn(), adjustShift: vi.fn() };
});

vi.mock('../src/lib/api/bridge', () => ({ api: {}, ready: Promise.resolve(), isMock: true }));
vi.mock('../src/views/timer/timerActions', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/views/timer/timerActions')>()),
  stopShiftAt: spies.stopShiftAt,
  adjustShift: spies.adjustShift,
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

  it('STOP ▾ works with the details folded', async () => {
    render(TimerView);
    await fireEvent.click(screen.getByRole('button', { name: 'Stop at an earlier time' }));
    expect(await screen.findByRole('dialog')).toBeTruthy();
  });
});

describe('running shift editors', () => {
  it('STOP ▾ saves the shift at the typed end time', async () => {
    render(TimerView);
    await fireEvent.click(screen.getByRole('button', { name: 'Stop at an earlier time' }));
    await submit('1630');
    expect(spies.stopShiftAt).toHaveBeenCalledWith('16:30');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('keeps the editor open on a time it cannot read', async () => {
    render(TimerView);
    await fireEvent.click(screen.getByRole('button', { name: 'Stop at an earlier time' }));
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
