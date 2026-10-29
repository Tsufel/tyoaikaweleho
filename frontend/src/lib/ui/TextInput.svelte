<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLInputAttributes } from 'svelte/elements';

  interface Props extends Omit<HTMLInputAttributes, 'value' | 'children' | 'size'> {
    value?: string;
    /** Red state (aria-invalid). */
    invalid?: boolean;
    /** Tabular mono digits (times, money). */
    mono?: boolean;
    size?: 'sm' | 'md';
    el?: HTMLInputElement;
    /** Content inside the field, right side (buttons/icons). */
    trailing?: Snippet;
    leading?: Snippet;
  }

  let {
    value = $bindable(''),
    invalid = false,
    mono = false,
    size = 'md',
    el = $bindable(),
    class: cls = '',
    trailing,
    leading,
    type = 'text',
    ...rest
  }: Props = $props();
</script>

<div class="field-box {size} {cls}" class:invalid class:has-trailing={!!trailing}>
  {#if leading}<span class="lead">{@render leading()}</span>{/if}
  <input
    bind:this={el}
    bind:value
    {type}
    class:mono
    aria-invalid={invalid || undefined}
    autocomplete="off"
    spellcheck="false"
    {...rest}
  />
  {#if trailing}<span class="trail">{@render trailing()}</span>{/if}
</div>

<style>
  .field-box {
    position: relative;
    display: flex;
    align-items: center;
    gap: 4px;
    height: 40px;
    padding: 0 4px 0 12px;
    border-radius: var(--radius-md);
    background: var(--field-bg);
    border: 1px solid var(--field-border);
    transition:
      border-color var(--dur-fast),
      background-color var(--dur-fast),
      box-shadow var(--dur-fast);
  }
  .sm {
    height: 32px;
    border-radius: var(--radius-sm);
    padding-left: 9px;
  }
  .field-box:not(.has-trailing) {
    padding-right: 12px;
  }
  .field-box:hover {
    border-color: color-mix(in srgb, var(--accent) 30%, var(--field-border));
  }
  .field-box:focus-within {
    background: var(--field-bg-focus);
    border-color: var(--accent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent);
  }
  .invalid,
  .invalid:hover,
  .invalid:focus-within {
    border-color: var(--danger);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--danger) 22%, transparent);
  }
  input {
    flex: 1;
    min-width: 0;
    height: 100%;
    border: 0;
    outline: none;
    background: transparent;
    font-size: var(--fs-md);
  }
  .sm input {
    font-size: var(--fs-sm);
  }
  input::placeholder {
    color: var(--text-subtle);
  }
  input.mono {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }
  input:focus-visible {
    outline: none;
  }
  .lead,
  .trail {
    display: flex;
    align-items: center;
    color: var(--text-muted);
  }
</style>
