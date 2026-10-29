import type { Action } from 'svelte/action';

/** Move the node to <body> (escapes backdrop-filter containing blocks). */
export const portal: Action<HTMLElement, HTMLElement | undefined> = (node, target) => {
  (target ?? document.body).appendChild(node);
  return {
    destroy() {
      node.remove();
    },
  };
};

/** Call `fn` on a pointerdown outside the node (and outside `ignore` elements). */
export const clickOutside: Action<
  HTMLElement,
  { fn: (e: PointerEvent) => void; ignore?: (HTMLElement | null | undefined)[] }
> = (node, params) => {
  let p = params;
  const onDown = (e: PointerEvent) => {
    const t = e.target as Node;
    if (node.contains(t)) return;
    if (p.ignore?.some((el) => el?.contains(t))) return;
    p.fn(e);
  };
  document.addEventListener('pointerdown', onDown, true);
  return {
    update(n) {
      p = n;
    },
    destroy() {
      document.removeEventListener('pointerdown', onDown, true);
    },
  };
};

export interface TooltipParams {
  text: string;
  /** Shortcut shown after the text, e.g. 'Ctrl+N'. */
  kbd?: string;
  placement?: 'top' | 'bottom';
}

let tipEl: HTMLDivElement | null = null;
let tipOwner: HTMLElement | null = null;
let showTimer: ReturnType<typeof setTimeout> | undefined;

function tipNode(): HTMLDivElement {
  if (tipEl) return tipEl;
  tipEl = document.createElement('div');
  tipEl.className = 'ui-tooltip';
  tipEl.setAttribute('role', 'tooltip');
  tipEl.id = 'ui-tooltip';
  document.body.appendChild(tipEl);
  return tipEl;
}

function hideTip(owner?: HTMLElement) {
  clearTimeout(showTimer);
  if (owner && owner !== tipOwner) return;
  tipOwner?.removeAttribute('aria-describedby');
  tipOwner = null;
  if (tipEl) tipEl.dataset.show = 'false';
}

/** `use:tooltip={'Text'}` or `use:tooltip={{text, kbd, placement}}`. */
export const tooltip: Action<HTMLElement, string | TooltipParams | null | undefined> = (node, params) => {
  let p: TooltipParams | null = typeof params === 'string' ? { text: params } : params ?? null;

  const show = (delay: number) => {
    clearTimeout(showTimer);
    if (!p?.text) return;
    showTimer = setTimeout(() => {
      if (!p?.text || !node.isConnected) return;
      const el = tipNode();
      el.textContent = p.text;
      if (p.kbd) {
        const k = document.createElement('kbd');
        k.textContent = p.kbd;
        el.appendChild(k);
      }
      el.dataset.show = 'true';
      tipOwner = node;
      node.setAttribute('aria-describedby', el.id);
      const r = node.getBoundingClientRect();
      const t = el.getBoundingClientRect();
      const below = p.placement === 'bottom' || (p.placement !== 'top' && r.top < t.height + 12);
      const left = Math.min(Math.max(8, r.left + r.width / 2 - t.width / 2), window.innerWidth - t.width - 8);
      el.style.left = `${left}px`;
      el.style.top = `${below ? r.bottom + 8 : r.top - t.height - 8}px`;
    }, delay);
  };
  const enter = () => show(450);
  const focus = () => {
    if (node.matches(':focus-visible')) show(150);
  };
  const leave = () => hideTip(node);

  node.addEventListener('pointerenter', enter);
  node.addEventListener('pointerleave', leave);
  node.addEventListener('pointerdown', leave);
  node.addEventListener('focus', focus);
  node.addEventListener('blur', leave);
  node.addEventListener('keydown', leave);
  return {
    update(n) {
      p = typeof n === 'string' ? { text: n } : n ?? null;
      if (tipOwner === node && tipEl && p?.text) tipEl.firstChild!.textContent = p.text;
    },
    destroy() {
      hideTip(node);
      node.removeEventListener('pointerenter', enter);
      node.removeEventListener('pointerleave', leave);
      node.removeEventListener('pointerdown', leave);
      node.removeEventListener('focus', focus);
      node.removeEventListener('blur', leave);
      node.removeEventListener('keydown', leave);
    },
  };
};

/** Focusable descendants in tab order. */
export function focusables(root: HTMLElement): HTMLElement[] {
  const sel =
    'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]), [contenteditable="true"]';
  return [...root.querySelectorAll<HTMLElement>(sel)].filter(
    (el) => !el.hasAttribute('inert') && el.getClientRects().length > 0,
  );
}
