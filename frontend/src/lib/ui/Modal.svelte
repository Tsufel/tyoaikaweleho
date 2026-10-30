<script lang="ts">
  import { onMount, tick, type Snippet } from 'svelte';
  import { pushModal, topModal } from '../stores/modals';
  import type { DialogIcon } from '../stores/confirm';
  import { fade, scale } from '../motion';
  import { focusables, portal } from './actions';
  import Icon from './Icon.svelte';
  import { liquidGlass } from '../glass/liquidGlass';

  interface Props {
    title?: string;
    /** Round badge left of the title. */
    icon?: DialogIcon;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    /** Escape / close button. Omit to make the modal non-dismissable. */
    onclose?: () => void;
    /** Show the × button (needs onclose). */
    closeButton?: boolean;
    /** Element or selector to focus first; default = first focusable in the body, then footer. */
    initialFocus?: HTMLElement | string | null;
    /** id of the element describing the dialog (aria-describedby). */
    describedby?: string;
    /** 'alertdialog' for confirms. */
    role?: 'dialog' | 'alertdialog';
    class?: string;
    header?: Snippet;
    footer?: Snippet;
    children?: Snippet;
  }

  let {
    title,
    icon,
    size = 'md',
    onclose,
    closeButton = false,
    initialFocus = null,
    describedby,
    role = 'dialog',
    class: cls = '',
    header,
    footer,
    children,
  }: Props = $props();

  const uid = Math.random().toString(36).slice(2, 8);
  const titleId = `modal-title-${uid}`;
  let panel = $state<HTMLDivElement>();
  let nudging = $state(false);
  let modalId = $state(-1);
  const isTop = $derived($topModal === modalId);

  function nudge() {
    focusFirst();
    nudging = false;
    requestAnimationFrame(() => (nudging = true));
    setTimeout(() => (nudging = false), 420);
  }

  function focusFirst() {
    if (!panel) return;
    if (panel.contains(document.activeElement) && document.activeElement !== panel) return;
    let target: HTMLElement | null = null;
    if (initialFocus instanceof HTMLElement) target = initialFocus;
    else if (typeof initialFocus === 'string') target = panel.querySelector<HTMLElement>(initialFocus);
    target ??= panel.querySelector<HTMLElement>('[data-autofocus]') ?? focusables(panel).find((el) => !el.closest('.modal-close')) ?? panel;
    target.focus();
    if (target instanceof HTMLInputElement && target.type === 'text') target.select();
  }

  function onKeydown(e: KeyboardEvent) {
    if (!isTop || !panel) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      if (onclose) onclose();
      else nudge();
      return;
    }
    if (e.key === 'Tab') {
      const items = focusables(panel);
      if (!items.length) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (!panel.contains(active)) {
        e.preventDefault();
        (e.shiftKey ? last : first).focus();
      } else if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  function onFocusIn(e: FocusEvent) {
    if (!isTop || !panel) return;
    const t = e.target as HTMLElement;
    if (panel.contains(t) || t.closest?.('[data-popover], .ui-tooltip')) return;
    focusFirst();
  }

  /** Backdrop click: the modal stays (v1.3 dialogs were modal) — nudge it instead. */
  function backdropDown(node: HTMLElement) {
    const down = (e: PointerEvent) => {
      if (e.target === node && isTop) {
        e.preventDefault();
        nudge();
      }
    };
    node.addEventListener('pointerdown', down);
    return { destroy: () => node.removeEventListener('pointerdown', down) };
  }

  onMount(() => {
    const previous = document.activeElement as HTMLElement | null;
    const handle = pushModal(nudge);
    modalId = handle.id;
    void tick().then(focusFirst);
    return () => {
      handle.release();
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  });

  const ICON_TONE: Record<DialogIcon, string> = {
    info: 'info',
    question: 'accent',
    warning: 'warning',
    error: 'danger',
    success: 'success',
  };
</script>

<svelte:window onkeydown={onKeydown} onfocusin={onFocusIn} />

<div class="modal-root" use:portal>
  <div class="backdrop" transition:fade={{ duration: 160 }} use:backdropDown></div>
  <div class="center">
    <div
      bind:this={panel}
      class="panel glass glass-strong lg-overlay {size} {cls}"
      class:nudge={nudging}
      {role}
      aria-modal="true"
      aria-labelledby={title ? titleId : undefined}
      aria-describedby={describedby}
      tabindex="-1"
      transition:scale={{ start: 0.94, duration: 240 }}
      use:liquidGlass={'modal'}
    >
      {#if header}
        {@render header()}
      {:else if title}
        <header class="head">
          {#if icon}
            <span class="badge {ICON_TONE[icon]}"><Icon name={icon} size={20} /></span>
          {/if}
          <h2 id={titleId}>{title}</h2>
          {#if closeButton && onclose}
            <button class="modal-close" type="button" aria-label="Close" onclick={() => onclose?.()}>
              <Icon name="x" size={18} />
            </button>
          {/if}
        </header>
      {/if}
      <div class="body">
        {@render children?.()}
      </div>
      {#if footer}
        <footer class="foot">
          {@render footer()}
        </footer>
      {/if}
    </div>
  </div>
</div>

<style>
  .modal-root {
    position: fixed;
    inset: 0;
    z-index: 100;
    pointer-events: none;
  }
  .backdrop {
    position: absolute;
    inset: 0;
    background: var(--scrim);
    backdrop-filter: blur(3px);
    pointer-events: auto;
  }
  /* Liquid glass: keep the page sharp enough for the panel's lens to bend */
  :global(:root[data-glass='liquid']) .backdrop {
    -webkit-backdrop-filter: blur(1.5px);
    backdrop-filter: blur(1.5px);
  }
  .center {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 24px;
    pointer-events: none;
  }
  .panel {
    pointer-events: auto;
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    max-height: calc(100vh - 48px);
    border-radius: var(--radius-xl);
    box-shadow: inset 0 1px 0 var(--glass-highlight), var(--shadow-lg);
    outline: none;
  }
  .sm {
    max-width: 420px;
  }
  .md {
    max-width: 520px;
  }
  .lg {
    max-width: 680px;
  }
  .xl {
    max-width: 880px;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 22px 24px 0;
  }
  h2 {
    flex: 1;
    font-size: var(--fs-lg);
    font-weight: 650;
    letter-spacing: -0.01em;
  }
  .badge {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border-radius: 12px;
    flex: none;
  }
  .badge.accent {
    color: var(--accent-text);
    background: color-mix(in srgb, var(--accent) 18%, transparent);
  }
  .badge.info {
    color: var(--info-text);
    background: color-mix(in srgb, var(--cyan) 16%, transparent);
  }
  .badge.warning {
    color: var(--warning-text);
    background: color-mix(in srgb, var(--amber) 18%, transparent);
  }
  .badge.danger {
    color: var(--danger-text);
    background: color-mix(in srgb, var(--danger) 18%, transparent);
  }
  .badge.success {
    color: var(--success-text);
    background: color-mix(in srgb, var(--success) 18%, transparent);
  }
  .modal-close {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }
  .modal-close:hover {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
  .body {
    padding: 16px 24px 20px;
    overflow: auto;
    min-height: 0;
  }
  .foot {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 10px;
    padding: 0 24px 22px;
  }
  .nudge {
    animation: nudge 0.4s var(--ease-out);
  }
  @keyframes nudge {
    20% {
      transform: translateX(-6px);
    }
    45% {
      transform: translateX(5px);
    }
    70% {
      transform: translateX(-3px);
    }
  }
</style>
