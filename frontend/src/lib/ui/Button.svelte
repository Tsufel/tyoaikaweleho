<script lang="ts" module>
  export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'success' | 'ghost';
</script>

<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  import Icon, { type IconName } from './Icon.svelte';
  import Spinner from './Spinner.svelte';
  import { tooltip as tip, type TooltipParams } from './actions';

  interface Props extends Omit<HTMLButtonAttributes, 'children'> {
    variant?: ButtonVariant;
    size?: 'sm' | 'md' | 'lg';
    /** Shows a spinner and disables the button. */
    loading?: boolean;
    /** Coloured glow (primary/danger/success). */
    glow?: boolean;
    icon?: IconName;
    iconRight?: IconName;
    /** Icon-only round/square button; requires `label`. */
    square?: boolean;
    /** aria-label (required for icon-only buttons). */
    label?: string;
    tooltip?: string | TooltipParams;
    full?: boolean;
    el?: HTMLButtonElement;
    children?: Snippet;
  }

  let {
    variant = 'secondary',
    size = 'md',
    loading = false,
    glow = false,
    icon,
    iconRight,
    square = false,
    label,
    tooltip,
    full = false,
    el = $bindable(),
    type = 'button',
    disabled,
    class: cls = '',
    children,
    ...rest
  }: Props = $props();

  const iconSize = $derived(size === 'sm' ? 15 : size === 'lg' ? 20 : 17);
</script>

<button
  bind:this={el}
  {type}
  class="btn {variant} {size} {cls}"
  class:glow
  class:square
  class:full
  class:loading
  disabled={disabled || loading}
  aria-label={label}
  aria-busy={loading || undefined}
  use:tip={tooltip}
  {...rest}
>
  {#if loading}
    <Spinner size={iconSize} />
  {:else if icon}
    <Icon name={icon} size={iconSize} />
  {/if}
  {#if children}<span class="text">{@render children()}</span>{/if}
  {#if iconRight}<Icon name={iconRight} size={iconSize} />{/if}
</button>

<style>
  .btn {
    --h: 38px;
    --px: 16px;
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: var(--h);
    padding: 0 var(--px);
    border-radius: var(--radius-md);
    border: 1px solid transparent;
    font-size: var(--fs-md);
    font-weight: 600;
    letter-spacing: 0.01em;
    white-space: nowrap;
    cursor: pointer;
    transition:
      transform var(--dur-fast) var(--ease-out),
      background-color var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-med) var(--ease-out),
      border-color var(--dur-fast) var(--ease-out),
      filter var(--dur-fast) var(--ease-out);
  }
  .sm {
    --h: 30px;
    --px: 11px;
    font-size: var(--fs-sm);
    border-radius: var(--radius-sm);
    gap: 6px;
  }
  .lg {
    --h: 48px;
    --px: 22px;
    font-size: var(--fs-lg);
    border-radius: var(--radius-lg);
  }
  .square {
    width: var(--h);
    padding: 0;
  }
  .full {
    width: 100%;
  }
  .text {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .primary {
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    color: var(--on-accent);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), var(--shadow-sm);
  }
  .danger {
    background: linear-gradient(135deg, var(--danger-strong), var(--danger-strong-2));
    color: var(--on-danger);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2), var(--shadow-sm);
  }
  .success {
    background: linear-gradient(135deg, var(--success-strong), var(--success-strong-2));
    color: var(--on-success);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25), var(--shadow-sm);
  }
  .secondary {
    background: var(--neutral-fill);
    color: var(--on-neutral);
    border-color: var(--glass-border);
  }
  .ghost {
    background: transparent;
    color: var(--text-muted);
  }

  .btn:not(:disabled):hover {
    transform: translateY(-1px);
  }
  .secondary:not(:disabled):hover,
  .ghost:not(:disabled):hover {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
  .primary:not(:disabled):hover,
  .danger:not(:disabled):hover,
  .success:not(:disabled):hover {
    filter: brightness(1.08) saturate(1.05);
  }
  .btn:not(:disabled):active {
    transform: scale(0.97);
    transition-duration: 60ms;
  }
  .glow.primary {
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 6px 24px -4px var(--accent-glow);
  }
  .glow.danger {
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 6px 24px -4px var(--danger-glow);
  }
  .glow.success {
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25), 0 6px 24px -4px var(--success-glow);
  }
  .glow:not(:disabled):hover {
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 10px 32px -4px var(--accent-glow);
  }
  .glow.danger:not(:disabled):hover {
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 10px 32px -4px var(--danger-glow);
  }
  .glow.success:not(:disabled):hover {
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25), 0 10px 32px -4px var(--success-glow);
  }
  .btn:disabled {
    cursor: default;
    opacity: 0.5;
  }
  .btn.loading:disabled {
    opacity: 0.85;
  }
  .btn:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
    border-radius: var(--radius-md);
  }
</style>
