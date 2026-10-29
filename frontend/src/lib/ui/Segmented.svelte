<script lang="ts" generics="T extends string">
  import type { IconName } from './Icon.svelte';
  import Icon from './Icon.svelte';

  /** Radiogroup with a sliding pill. ←/→ move and select (roving tabindex). */
  let {
    value = $bindable(),
    options,
    label,
    size = 'md',
    onchange,
    class: cls = '',
  }: {
    value: T;
    options: { value: T; label: string; icon?: IconName; hint?: string }[];
    label: string;
    size?: 'sm' | 'md';
    onchange?: (v: T) => void;
    class?: string;
  } = $props();

  let root = $state<HTMLElement>();
  let pill = $state({ x: 0, w: 0, ready: false });

  function measure() {
    const btn = root?.querySelector<HTMLElement>('[aria-checked="true"]');
    if (!btn) return;
    pill = { x: btn.offsetLeft, w: btn.offsetWidth, ready: true };
  }

  $effect(() => {
    void value;
    measure();
  });

  $effect(() => {
    if (!root) return;
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    return () => ro.disconnect();
  });

  function select(v: T) {
    if (v === value) return;
    value = v;
    onchange?.(v);
  }

  function onKeydown(e: KeyboardEvent) {
    const i = options.findIndex((o) => o.value === value);
    let n = i;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') n = (i + 1) % options.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') n = (i - 1 + options.length) % options.length;
    else if (e.key === 'Home') n = 0;
    else if (e.key === 'End') n = options.length - 1;
    else return;
    e.preventDefault();
    select(options[n].value);
    root?.querySelectorAll<HTMLElement>('[role="radio"]')[n]?.focus();
  }
</script>

<div bind:this={root} class="seg {size} {cls}" role="radiogroup" aria-label={label} tabindex="-1" onkeydown={onKeydown}>
  <span class="pill" class:ready={pill.ready} style:transform="translateX({pill.x}px)" style:width="{pill.w}px"></span>
  {#each options as o (o.value)}
    <button
      type="button"
      role="radio"
      aria-checked={o.value === value}
      tabindex={o.value === value ? 0 : -1}
      title={o.hint}
      onclick={() => select(o.value)}
    >
      {#if o.icon}<Icon name={o.icon} size={size === 'sm' ? 14 : 16} />{/if}
      <span>{o.label}</span>
    </button>
  {/each}
</div>

<style>
  .seg {
    position: relative;
    display: inline-flex;
    padding: 3px;
    gap: 2px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
    border: 1px solid var(--glass-border);
    outline: none;
  }
  .pill {
    position: absolute;
    top: 3px;
    bottom: 3px;
    left: 0;
    border-radius: var(--radius-pill);
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    box-shadow: 0 2px 10px var(--accent-glow);
    opacity: 0;
  }
  .pill.ready {
    opacity: 1;
    transition:
      transform var(--dur-med) var(--ease-spring),
      width var(--dur-med) var(--ease-spring);
  }
  button {
    position: relative;
    z-index: 1;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 14px;
    border: 0;
    border-radius: var(--radius-pill);
    background: transparent;
    color: var(--text-muted);
    font-weight: 600;
    font-size: var(--fs-sm);
    cursor: pointer;
    white-space: nowrap;
    transition: color var(--dur-fast);
  }
  .sm button {
    height: 26px;
    padding: 0 10px;
    font-size: var(--fs-xs);
  }
  button:hover {
    color: var(--text);
  }
  button[aria-checked='true'] {
    color: var(--on-accent);
  }
</style>
