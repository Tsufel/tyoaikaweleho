import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { flushSync } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StartDial from '../src/views/timer/StartDial.svelte';

// 10:03:20; jsdom lays the dial out as a zero box, so the ring's centre is (0, 0)
const NOW = new Date(2026, 9, 30, 10, 3, 20).getTime();

function renderDial() {
  render(StartDial, { props: { picked: null, now: NOW, targetHours: 8, onstart: () => {} } });
  flushSync();
  const dial = screen.getByRole('slider');
  return { dial, hit: dial.querySelector('circle.hit')!, offset: () => Number(dial.getAttribute('aria-valuenow')) };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(NOW);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('start dial: first step back from now', () => {
  it('a wheel notch up goes back to the previous 5-minute mark', async () => {
    const { dial, offset } = renderDial();
    await fireEvent.wheel(dial, { deltaY: -100 });
    expect(dial.getAttribute('aria-valuetext')).toBe('Start at 10:00, 3m ago');
    expect(offset()).toBe(3);
  });

  it('pressing the knob a hair clockwise of 12 stays at now instead of jumping a lap', async () => {
    const { dial, hit, offset } = renderDial();
    await fireEvent.pointerDown(hit, { button: 0, pointerId: 1, clientX: 3, clientY: -100 });
    expect(dial.getAttribute('aria-valuetext')).toBe('Start now');
    expect(offset()).toBe(0);
  });

  it('dragging anticlockwise from that press steps back minutes, like the wheel', async () => {
    const { dial, hit, offset } = renderDial();
    await fireEvent.pointerDown(hit, { button: 0, pointerId: 1, clientX: 3, clientY: -100 });
    await fireEvent.pointerMove(hit, { pointerId: 1, clientX: -3, clientY: -100 });
    // ≈ 0.5% of an 8 h lap: the first 5-minute mark back
    expect(dial.getAttribute('aria-valuetext')).toBe('Start at 10:00, 3m ago');
    await fireEvent.pointerMove(hit, { pointerId: 1, clientX: -20, clientY: -100 });
    expect(offset()).toBeGreaterThan(0);
    expect(offset()).toBeLessThan(20);
    await fireEvent.pointerUp(hit, { pointerId: 1 });
  });
});
