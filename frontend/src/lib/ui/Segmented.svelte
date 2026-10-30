<script lang="ts" generics="T extends string">
  import { untrack } from 'svelte';
  import { liquidGlass, pulseLens } from '../glass/liquidGlass';
  import { glassLive } from '../stores/glass';
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
  let pillEl = $state<HTMLElement>();

  // Liquid glass: while the pill travels it turns into a clear magnifying
  // lens above the labels (only with full motion; inert otherwise).
  let moving = $state(false);
  /** The pill's own refraction lens is attached (refract tier, slot granted). */
  let lensed = $state(false);
  let moveTimer: ReturnType<typeof setTimeout> | undefined;
  const onlens = (on: boolean) => (lensed = on);

  function startMoving() {
    moving = true;
    clearTimeout(moveTimer);
    moveTimer = setTimeout(() => (moving = false), 450);
  }

  function stopMoving(e: TransitionEvent) {
    if (e.target !== pillEl || e.propertyName !== 'transform') return;
    clearTimeout(moveTimer);
    moving = false;
  }

  function onPointerDown() {
    if (!$glassLive) return;
    startMoving();
    pulseLens(pillEl);
  }

  $effect(() => () => clearTimeout(moveTimer));

  function measure() {
    const btn = root?.querySelector<HTMLElement>('[aria-checked="true"]');
    if (!btn) return;
    const x = btn.offsetLeft;
    // untracked: measure runs inside the value effect and must not depend on pill
    untrack(() => {
      if (pill.ready && x !== pill.x && $glassLive) startMoving();
    });
    pill = { x, w: btn.offsetWidth, ready: true };
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
  <span
    bind:this={pillEl}
    class="pill"
    class:ready={pill.ready}
    class:moving
    class:lensed
    style:transform="translateX({pill.x}px)"
    style:width="{pill.w}px"
    ontransitionend={stopMoving}
    use:liquidGlass={{ key: 'pill', active: moving, onlens }}
  ></span>
  {#each options as o (o.value)}
    <button
      type="button"
      role="radio"
      aria-checked={o.value === value}
      tabindex={o.value === value ? 0 : -1}
      title={o.hint}
      onpointerdown={onPointerDown}
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

  /* Liquid glass: the track is a well; the thumb is an iOS-style glass
     platter (::before) with the selected label in the tint colour. While
     moving with its own lens attached (refract tier) the clear lens rides
     above the labels and magnifies them. Without a lens (CSS tier, no slot)
     the platter stays. */
  :global(:root[data-glass='liquid']) .seg {
    box-shadow: inset 0 1px 2px var(--lg-well);
  }
  :global(:root[data-glass='liquid']) .pill {
    background: var(--lg-lens-tint);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.4),
      inset 0 -1px 0 rgba(0, 0, 0, 0.12),
      0 2px 8px rgba(0, 0, 0, 0.18);
  }
  :global(:root[data-glass='liquid']) .pill::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0) 55%),
      var(--lg-platter);
    transition: opacity 160ms var(--ease-out);
  }
  :global(:root[data-glass='liquid']) button[aria-checked='true'] {
    color: var(--accent-text);
  }
  :global(:root[data-glass='liquid']) .pill.moving {
    pointer-events: none;
    animation: lg-stretch 320ms var(--ease-out);
  }
  :global(:root[data-refract='on']) .pill.moving.lensed {
    z-index: 2;
    -webkit-backdrop-filter: var(--lg-filter, none);
    backdrop-filter: var(--lg-filter, none);
  }
  :global(:root[data-refract='on']) .pill.moving.lensed::before {
    opacity: 0;
  }
  :global(:root[data-refract='on']) .seg:has(.pill.moving.lensed) button[aria-checked='true'] {
    color: var(--text);
  }
  @keyframes -global-lg-stretch {
    35% {
      scale: 1.1 0.88;
    }
    100% {
      scale: 1 1;
    }
  }
</style>
