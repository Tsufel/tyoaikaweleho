<script lang="ts">
  import { onDestroy } from 'svelte';
  import { dismiss, runToastAction, toasts, type Toast } from '../stores/toasts';
  import { pageVisible, windowFocused } from '../stores/app';
  import { fly, flip } from '../motion';
  import Icon, { type IconName } from './Icon.svelte';
  import { liquidGlass } from '../glass/liquidGlass';
  import { createToastTimers } from './toastTimers';

  // per-toast countdowns; paused while hovered, focused or the window is away
  const timers = createToastTimers(dismiss);
  let stackEl = $state<HTMLElement>();

  $effect(() => {
    timers.sync($toasts);
  });
  $effect(() => {
    timers.hold('away', !$windowFocused || !$pageVisible);
  });

  function focusOut(e: FocusEvent) {
    const next = e.relatedTarget as Node | null;
    if (!next || !stackEl?.contains(next)) timers.hold('focus', false);
  }

  onDestroy(() => timers.destroy());

  const ICONS: Record<Toast['tone'], IconName> = {
    info: 'info',
    success: 'success',
    warning: 'warning',
    error: 'error',
  };
</script>

<section
  bind:this={stackEl}
  class="toasts"
  aria-label="Notifications"
  onpointerenter={() => timers.hold('hover', true)}
  onpointerleave={() => timers.hold('hover', false)}
  onfocusin={() => timers.hold('focus', true)}
  onfocusout={focusOut}
>
  <div aria-live="polite" aria-atomic="false" class="stack">
    {#each $toasts as t (t.id)}
      <div
        class="toast glass glass-strong lg-float {t.tone}"
        role={t.tone === 'error' ? 'alert' : 'status'}
        in:fly={{ y: 16 }}
        out:fly={{ y: 8, duration: 160 }}
        animate:flip
        use:liquidGlass={'toast'}
      >
        <span class="ic"><Icon name={ICONS[t.tone]} size={18} /></span>
        <span class="msg">{t.message}</span>
        {#if t.count > 1}
          <span class="count"><span aria-hidden="true">×{t.count}</span><span class="sr-only">({t.count} times)</span></span>
        {/if}
        {#if t.action}
          <button type="button" class="action" onclick={() => runToastAction(t.id)}>{t.label}</button>
        {/if}
        <button type="button" class="close" aria-label="Dismiss" onclick={() => dismiss(t.id)}>
          <Icon name="x" size={15} />
        </button>
      </div>
    {/each}
  </div>
</section>

<style>
  .toasts {
    position: fixed;
    left: 50%;
    bottom: 20px;
    transform: translateX(-50%);
    z-index: 200;
    width: min(520px, calc(100vw - 32px));
    pointer-events: none;
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: center;
  }
  .toast {
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 10px 10px 14px;
    border-radius: var(--radius-md);
    box-shadow: inset 0 1px 0 var(--glass-highlight), var(--shadow-lg);
    font-size: var(--fs-sm);
  }
  .ic {
    display: grid;
    color: var(--info-text);
  }
  .success .ic {
    color: var(--success-text);
  }
  .warning .ic {
    color: var(--warning-text);
  }
  .error .ic {
    color: var(--danger-text);
  }
  .msg {
    flex: 1;
    min-width: 0;
    line-height: 1.4;
    white-space: pre-line;
  }
  .count {
    flex: none;
    padding: 2px 7px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
    color: var(--text-muted);
    font-size: var(--fs-xs);
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }
  .action {
    border: 0;
    border-radius: 9px;
    padding: 6px 12px;
    background: color-mix(in srgb, var(--accent) 20%, transparent);
    color: var(--accent-text);
    font-weight: 650;
    cursor: pointer;
    transition: background-color var(--dur-fast);
  }
  .action:hover {
    background: color-mix(in srgb, var(--accent) 32%, transparent);
  }
  .close {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }
  .close:hover {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
</style>
