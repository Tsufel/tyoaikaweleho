<script lang="ts">
  import { parseTimeInput } from '../time';
  import Icon from './Icon.svelte';
  import Popover from './Popover.svelte';
  import TextInput from './TextInput.svelte';
  import TimePicker from './TimePicker.svelte';

  /** HH:MM text field with a clock button opening the 48-slot picker.
   *  Normalises loose input ("830", "8.30", "8") on blur; leaves invalid
   *  text untouched so the caller can flag it. */
  let {
    value = $bindable(''),
    id,
    label,
    invalid = false,
    placeholder = 'HH:MM',
    disabled = false,
    size = 'md',
    el = $bindable(),
    onchange,
    describedby,
  }: {
    value?: string;
    id?: string;
    label?: string;
    invalid?: boolean;
    placeholder?: string;
    disabled?: boolean;
    size?: 'sm' | 'md';
    el?: HTMLInputElement;
    onchange?: (v: string) => void;
    describedby?: string;
  } = $props();

  let open = $state(false);
  let btn = $state<HTMLButtonElement>();

  function normalise() {
    const t = parseTimeInput(value);
    if (t && t !== value) value = t;
    onchange?.(value);
  }

  function pick(t: string) {
    value = t;
    open = false;
    onchange?.(t);
    el?.focus();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' && e.altKey) {
      e.preventDefault();
      open = true;
    }
  }
</script>

<TextInput
  bind:value
  bind:el
  {id}
  {invalid}
  {placeholder}
  {disabled}
  {size}
  mono
  inputmode="numeric"
  maxlength={5}
  aria-label={label}
  aria-describedby={describedby}
  onblur={normalise}
  onkeydown={onKeydown}
  class="time-input"
>
  {#snippet trailing()}
    <button
      bind:this={btn}
      type="button"
      class="clock"
      aria-label="Choose time"
      aria-haspopup="listbox"
      aria-expanded={open}
      {disabled}
      onclick={() => (open = !open)}
    >
      <Icon name="clock" size={16} />
    </button>
  {/snippet}
</TextInput>

{#if open}
  <Popover anchor={btn} onclose={() => (open = false)} placement="bottom-end" role="none">
    <TimePicker value={parseTimeInput(value)} onpick={pick} label={label ? `${label}: pick a time` : 'Pick a time'} />
  </Popover>
{/if}

<style>
  .clock {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition:
      background-color var(--dur-fast),
      color var(--dur-fast);
  }
  .clock:hover,
  .clock[aria-expanded='true'] {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
  .clock:disabled {
    opacity: 0.5;
    cursor: default;
  }
  :global(.time-input) {
    width: 132px;
  }
</style>
