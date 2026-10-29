<script lang="ts">
  import { onDestroy } from 'svelte';
  import { dismiss, runToastAction, toasts, type Toast } from '../stores/toasts';
  import { fly, flip } from '../motion';
  import Icon, { type IconName } from './Icon.svelte';

  // per-toast countdown that pauses while hovered / focused
  const timers = new Map<number, { left: number; started: number; handle?: ReturnType<typeof setTimeout> }>();
  let hovering = $state(false);

  function arm(t: Toast) {
    if (t.ms <= 0) return;
    const s = timers.get(t.id) ?? { left: t.ms, started: 0 };
    timers.set(t.id, s);
    if (hovering || s.handle) return;
    s.started = Date.now();
    s.handle = setTimeout(() => dismiss(t.id), s.left);
  }

  function pauseAll() {
    hovering = true;
    for (const s of timers.values()) {
      if (!s.handle) continue;
      clearTimeout(s.handle);
      s.handle = undefined;
      s.left = Math.max(1500, s.left - (Date.now() - s.started));
    }
  }

  function resumeAll() {
    hovering = false;
    for (const t of $toasts) arm(t);
  }

  $effect(() => {
    const ids = new Set($toasts.map((t) => t.id));
    for (const [id, s] of timers) {
      if (!ids.has(id)) {
        clearTimeout(s.handle);
        timers.delete(id);
      }
    }
    for (const t of $toasts) arm(t);
  });

  onDestroy(() => {
    for (const s of timers.values()) clearTimeout(s.handle);
  });

  const ICONS: Record<Toast['tone'], IconName> = {
    info: 'info',
    success: 'success',
    warning: 'warning',
    error: 'error',
  };
</script>

<section
  class="toasts"
  aria-label="Notifications"
  onpointerenter={pauseAll}
  onpointerleave={resumeAll}
  onfocusin={pauseAll}
  onfocusout={resumeAll}
>
  <div aria-live="polite" aria-atomic="false" class="stack">
    {#each $toasts as t (t.id)}
      <div class="toast glass glass-strong {t.tone}" role={t.tone === 'error' ? 'alert' : 'status'} in:fly={{ y: 16 }} out:fly={{ y: 8, duration: 160 }} animate:flip>
        <span class="ic"><Icon name={ICONS[t.tone]} size={18} /></span>
        <span class="msg">{t.message}</span>
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
