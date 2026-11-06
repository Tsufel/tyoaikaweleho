import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearToasts, toast, toasts, trimToasts, type Toast } from '../src/lib/stores/toasts';
import { createToastTimers, RESUME_MIN_MS } from '../src/lib/ui/toastTimers';

const messages = () => get(toasts).map((t) => t.message);

describe('toast stack', () => {
  beforeEach(() => clearToasts());

  it('keeps a sticky toast when newer ones push past the cap', () => {
    toast('Your hours file was damaged', { tone: 'warning', ms: 0 });
    for (let i = 1; i <= 5; i++) toast(`note ${i}`);
    expect(messages()).toEqual(['Your hours file was damaged', 'note 3', 'note 4', 'note 5']);
  });

  it('drops the oldest sticky toast only when every older one is sticky', () => {
    for (let i = 1; i <= 4; i++) toast(`sticky ${i}`, { ms: 0 });
    toast('fresh');
    expect(messages()).toEqual(['sticky 2', 'sticky 3', 'sticky 4', 'fresh']);
  });

  it('trimToasts never drops the newest toast', () => {
    const mk = (id: number, ms: number): Toast => ({ id, message: `${id}`, tone: 'info', undo: true, ms, count: 1 });
    const out = trimToasts([mk(1, 0), mk(2, 0), mk(3, 8000)], 2);
    expect(out.map((t) => t.id)).toEqual([2, 3]);
  });

  it('collapses an identical plain toast into a counter', () => {
    const a = toast('Could not save', { tone: 'error' });
    const b = toast('Could not save', { tone: 'error' });
    toast('Could not save', { tone: 'error' });
    expect(b).toBe(a);
    expect(get(toasts)).toHaveLength(1);
    expect(get(toasts)[0].count).toBe(3);
  });

  it('keeps toasts apart when tone or action differ', () => {
    toast('Saved', { tone: 'success' });
    toast('Saved', { tone: 'info' });
    toast('Saved', { tone: 'success', action: () => {} });
    toast('Saved', { tone: 'success', action: () => {} });
    expect(get(toasts)).toHaveLength(4);
  });

  it('a repeat of a sticky toast stays sticky', () => {
    toast('Damaged file', { ms: 0 });
    toast('Damaged file');
    expect(get(toasts)[0]).toMatchObject({ ms: 0, count: 2 });
  });
});

describe('toast countdowns', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('expires each toast after its time', () => {
    const gone = vi.fn();
    const t = createToastTimers(gone);
    t.sync([{ id: 1, ms: 8000 }, { id: 2, ms: 0 }]);
    vi.advanceTimersByTime(7999);
    expect(gone).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(gone).toHaveBeenCalledWith(1);
    vi.advanceTimersByTime(60_000);
    expect(gone).toHaveBeenCalledTimes(1); // the sticky one stays
  });

  it('pauses while the window is away and resumes with at least 3 s', () => {
    const gone = vi.fn();
    const t = createToastTimers(gone);
    t.sync([{ id: 1, ms: 8000 }]);
    vi.advanceTimersByTime(7000);
    t.hold('away', true);
    vi.advanceTimersByTime(60_000);
    expect(gone).not.toHaveBeenCalled();
    t.hold('away', false);
    vi.advanceTimersByTime(RESUME_MIN_MS - 1);
    expect(gone).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(gone).toHaveBeenCalledWith(1);
  });

  it('keeps hover and window holds apart', () => {
    const gone = vi.fn();
    const t = createToastTimers(gone);
    t.sync([{ id: 1, ms: 8000 }]);
    t.hold('hover', true);
    t.hold('away', true);
    t.hold('hover', false); // still away: no countdown
    vi.advanceTimersByTime(20_000);
    expect(gone).not.toHaveBeenCalled();
    expect(t.paused).toBe(true);
    t.hold('away', false);
    vi.advanceTimersByTime(8000);
    expect(gone).toHaveBeenCalledTimes(1);
  });

  it('starts the full time again when a duplicate bumps the count', () => {
    const gone = vi.fn();
    const t = createToastTimers(gone);
    t.sync([{ id: 1, ms: 8000, count: 1 }]);
    vi.advanceTimersByTime(6000);
    t.sync([{ id: 1, ms: 8000, count: 2 }]);
    vi.advanceTimersByTime(6000);
    expect(gone).not.toHaveBeenCalled();
    vi.advanceTimersByTime(2000);
    expect(gone).toHaveBeenCalledWith(1);
  });

  it('forgets toasts that were dismissed', () => {
    const gone = vi.fn();
    const t = createToastTimers(gone);
    t.sync([{ id: 1, ms: 8000 }]);
    t.sync([]);
    vi.advanceTimersByTime(10_000);
    expect(gone).not.toHaveBeenCalled();
  });
});
