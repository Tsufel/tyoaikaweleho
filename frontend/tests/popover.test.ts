import { cleanup, render } from '@testing-library/svelte';
import { createRawSnippet, tick } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/lib/api/bridge', () => ({ api: {}, ready: Promise.resolve(), isMock: () => true }));
vi.mock('../src/lib/stores/settings', async () => {
  const { writable } = await import('svelte/store');
  // Reduced motion: transitions are instant, so jsdom needs no Web Animations.
  return { settings: writable({ ui_prefs: { reduce_effects: true, lulz: false } }) };
});

const Popover = (await import('../src/lib/ui/Popover.svelte')).default;
const { restoreFocusLater, tooltip } = await import('../src/lib/ui/actions');

const body = createRawSnippet(() => ({ render: () => '<div><button class="inside">One</button></div>' }));

function button(label: string): HTMLButtonElement {
  const b = document.createElement('button');
  b.textContent = label;
  document.body.append(b);
  return b;
}

describe('Popover focus-out', () => {
  beforeEach(() => {
    globalThis.ResizeObserver ??= class {
      observe() {}
      disconnect() {}
      unobserve() {}
    } as unknown as typeof ResizeObserver;
  });
  afterEach(() => {
    cleanup();
    document.body.innerHTML = '';
  });

  async function open(props: Record<string, unknown> = {}) {
    const anchor = button('Anchor');
    const outside = button('Outside');
    const onclose = vi.fn();
    render(Popover, { props: { anchor, onclose, children: body, ...props } });
    await tick();
    const inside = document.querySelector<HTMLButtonElement>('[data-popover] .inside')!;
    inside.focus();
    return { anchor, outside, inside, onclose };
  }

  const settle = () => new Promise((r) => setTimeout(r, 5));

  it('closes when focus moves to something outside', async () => {
    const { outside, onclose } = await open();
    outside.focus();
    await settle();
    expect(onclose).toHaveBeenCalledTimes(1);
  });

  it('stays open when focus goes back to the anchor', async () => {
    const { anchor, onclose } = await open();
    anchor.focus();
    await settle();
    expect(onclose).not.toHaveBeenCalled();
  });

  it('stays open when focus only drops to the page', async () => {
    const { inside, onclose } = await open();
    inside.blur();
    await settle();
    expect(onclose).not.toHaveBeenCalled();
  });

  it('can be told to ignore focus-out', async () => {
    const { outside, onclose } = await open({ closeOnFocusOut: false });
    outside.focus();
    await settle();
    expect(onclose).not.toHaveBeenCalled();
  });
});

describe('restoreFocusLater', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('waits a task, then focuses the opener once the shell is no longer inert', async () => {
    const shell = document.createElement('div');
    shell.setAttribute('inert', '');
    const opener = document.createElement('button');
    shell.append(opener);
    document.body.append(shell);
    const order: string[] = [];
    const focus = vi.spyOn(opener, 'focus').mockImplementation(() => {
      order.push(shell.hasAttribute('inert') ? 'focus while inert' : 'focus');
    });
    restoreFocusLater(opener, null);
    // the modal store releases and Svelte clears inert in a microtask
    queueMicrotask(() => shell.removeAttribute('inert'));
    expect(focus).not.toHaveBeenCalled();
    await new Promise((r) => setTimeout(r, 5));
    expect(order).toEqual(['focus']);
  });

  it('leaves focus alone when something else took it', async () => {
    const opener = button('Opener');
    const other = button('Other');
    restoreFocusLater(opener, null);
    other.focus();
    await new Promise((r) => setTimeout(r, 5));
    expect(document.activeElement).toBe(other);
  });

  it('takes focus back from the closing panel', async () => {
    const opener = button('Opener');
    const panel = document.createElement('div');
    const inPanel = document.createElement('button');
    panel.append(inPanel);
    document.body.append(panel);
    inPanel.focus();
    restoreFocusLater(opener, panel);
    await new Promise((r) => setTimeout(r, 5));
    expect(document.activeElement).toBe(opener);
  });
});

describe('tooltip', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = '';
  });

  it('hides when the page scrolls or the window loses focus', () => {
    const owner = button('Owner');
    const t = tooltip(owner, { text: 'Hello' });
    const shown = () => document.querySelector<HTMLElement>('.ui-tooltip')?.dataset.show;
    owner.dispatchEvent(new Event('pointerenter'));
    vi.advanceTimersByTime(500);
    expect(shown()).toBe('true');
    document.body.dispatchEvent(new Event('scroll'));
    expect(shown()).toBe('false');
    owner.dispatchEvent(new Event('pointerenter'));
    vi.advanceTimersByTime(500);
    window.dispatchEvent(new Event('blur'));
    expect(shown()).toBe('false');
    t?.destroy?.();
  });
});
