import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/lib/api/bridge', () => ({ api: {}, ready: Promise.resolve(), isMock: () => true }));

const { registerCommand, runCommand, hasCommand, startShortcuts, isTyping } = await import('../src/lib/shortcuts');
const { route } = await import('../src/lib/stores/app');
const { pushModal } = await import('../src/lib/stores/modals');
const { toast, clearToasts } = await import('../src/lib/stores/toasts');

type Cmd = Parameters<typeof registerCommand>[0];

const stop = startShortcuts();
afterAll(() => stop());

let unregister: (() => void)[] = [];
const bind = (name: Cmd) => {
  const fn = vi.fn();
  unregister.push(registerCommand(name, fn));
  return fn;
};

/** Dispatch a keydown on `target` (bubbles to window); returns the event. */
function press(key: string, opts: KeyboardEventInit = {}, target: EventTarget = document.body): KeyboardEvent {
  const e = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...opts });
  target.dispatchEvent(e);
  return e;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Record<string, string> = {}, parent: Element = document.body) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  parent.appendChild(node);
  return node;
}

beforeEach(() => {
  route.set('main');
  clearToasts();
});

afterEach(() => {
  unregister.forEach((u) => u());
  unregister = [];
  document.body.innerHTML = '';
});

describe('commands', () => {
  it('the newest handler wins, and unregistering restores the previous one', () => {
    const first = bind('export');
    const second = bind('export');
    expect(runCommand('export')).toBe(true);
    expect(second).toHaveBeenCalledOnce();
    expect(first).not.toHaveBeenCalled();
    unregister.pop()!();
    runCommand('export');
    expect(first).toHaveBeenCalledOnce();
  });

  it('runCommand is false when nothing is bound', () => {
    expect(hasCommand('month.current')).toBe(false);
    expect(runCommand('month.current')).toBe(false);
  });
});

describe('global keys', () => {
  it('F5 toggles the timer on main and stats, not in settings', () => {
    const toggle = bind('timer.toggle');
    press('F5');
    route.set('stats');
    press('F5');
    expect(toggle).toHaveBeenCalledTimes(2);
    route.set('settings');
    const e = press('F5');
    expect(toggle).toHaveBeenCalledTimes(2);
    expect(e.defaultPrevented).toBe(true); // never reloads the page
  });

  it('Ctrl+N is blocked while a modal is open but still prevents a new window', () => {
    const add = bind('entry.add');
    const modal = pushModal(() => {});
    try {
      const e = press('n', { ctrlKey: true });
      expect(e.defaultPrevented).toBe(true);
      expect(add).not.toHaveBeenCalled();
    } finally {
      modal.release();
    }
    press('n', { ctrlKey: true });
    expect(add).toHaveBeenCalledOnce();
  });

  it('a key a focused component already handled is left alone', () => {
    const add = bind('entry.add');
    const input = el('input');
    input.addEventListener('keydown', (e) => e.preventDefault());
    press('n', { ctrlKey: true }, input);
    expect(add).not.toHaveBeenCalled();
  });

  it('typing keys stay with text fields unless the binding allows typing', () => {
    const prev = bind('month.prev');
    const add = bind('entry.add');
    const input = el('input', { type: 'text' });
    press('PageUp', {}, input);
    expect(prev).not.toHaveBeenCalled();
    press('n', { ctrlKey: true }, input);
    expect(add).toHaveBeenCalledOnce();
    press('PageUp', {}, el('input', { type: 'checkbox' }));
    expect(prev).toHaveBeenCalledOnce();
  });

  it('key repeat only steps months', () => {
    const prev = bind('month.prev');
    const add = bind('entry.add');
    press('ArrowLeft', { ctrlKey: true, repeat: true });
    press('PageUp', { repeat: true });
    expect(prev).toHaveBeenCalledTimes(2);
    press('n', { ctrlKey: true, repeat: true });
    expect(add).not.toHaveBeenCalled();
  });

  it('Alt combinations are never shortcuts', () => {
    const prev = bind('month.prev');
    const e = press('PageUp', { altKey: true });
    expect(prev).not.toHaveBeenCalled();
    expect(e.defaultPrevented).toBe(false);
  });

  it('Ctrl+Z only runs while an undo toast is showing', () => {
    const undo = bind('undo');
    let e = press('z', { ctrlKey: true });
    expect(undo).not.toHaveBeenCalled();
    expect(e.defaultPrevented).toBe(false); // the browser's own undo still works
    toast('Shift deleted', { action: () => {} });
    e = press('z', { ctrlKey: true });
    expect(undo).toHaveBeenCalledOnce();
    expect(e.defaultPrevented).toBe(true);
  });

  it('a plain link toast (undo: false) does not enable Ctrl+Z', () => {
    const undo = bind('undo');
    toast('Exported', { action: () => {}, label: 'View', undo: false });
    press('z', { ctrlKey: true });
    expect(undo).not.toHaveBeenCalled();
  });

  it('Ctrl+S saves only in settings; Esc goes back only from settings', () => {
    const save = bind('settings.save');
    const back = bind('settings.back');
    press('s', { ctrlKey: true });
    press('Escape');
    expect(save).not.toHaveBeenCalled();
    expect(back).not.toHaveBeenCalled();
    route.set('settings');
    press('s', { ctrlKey: true });
    press('Escape', {}, el('input', { type: 'text' }));
    expect(save).toHaveBeenCalledOnce();
    expect(back).toHaveBeenCalledOnce();
  });
});

describe('shifts table keys', () => {
  it('Enter, F2 and Del work only with focus inside the table', () => {
    const edit = bind('entry.edit');
    const del = bind('entry.delete');
    press('Enter');
    press('Delete');
    expect(edit).not.toHaveBeenCalled();
    expect(del).not.toHaveBeenCalled();
    const table = el('div', { 'data-entries-table': '' });
    const row = el('div', { tabindex: '0' }, table);
    press('Enter', {}, row);
    press('F2', {}, row);
    press('Delete', {}, row);
    expect(edit).toHaveBeenCalledTimes(2);
    expect(del).toHaveBeenCalledOnce();
  });

  it('Enter on a button inside the table activates the button, not edit', () => {
    const edit = bind('entry.edit');
    const table = el('div', { 'data-entries-table': '' });
    const button = el('button', {}, table);
    press('Enter', {}, button);
    expect(edit).not.toHaveBeenCalled();
    press('F2', {}, button);
    expect(edit).toHaveBeenCalledOnce();
  });
});

describe('isTyping', () => {
  it('knows text fields from other controls', () => {
    expect(isTyping(el('input'))).toBe(true);
    expect(isTyping(el('textarea'))).toBe(true);
    expect(isTyping(el('select'))).toBe(true);
    expect(isTyping(el('input', { type: 'range' }))).toBe(false);
    expect(isTyping(el('button'))).toBe(false);
    expect(isTyping(null)).toBe(false);
  });
});
