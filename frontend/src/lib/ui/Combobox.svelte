<script lang="ts">
  import Icon from './Icon.svelte';
  import Popover from './Popover.svelte';
  import TextInput from './TextInput.svelte';

  /** Editable dropdown (shift names etc.). With allowCustom=false the value
   *  snaps back to the last valid option on blur. */
  let {
    value = $bindable(''),
    options,
    allowCustom = true,
    id,
    label,
    placeholder,
    invalid = false,
    disabled = false,
    size = 'md',
    el = $bindable(),
    onchange,
    describedby,
  }: {
    value?: string;
    options: string[];
    allowCustom?: boolean;
    id?: string;
    label?: string;
    placeholder?: string;
    invalid?: boolean;
    disabled?: boolean;
    size?: 'sm' | 'md';
    el?: HTMLInputElement;
    onchange?: (v: string) => void;
    describedby?: string;
  } = $props();

  const listId = `cb-${Math.random().toString(36).slice(2, 8)}`;
  let open = $state(false);
  let active = $state(-1);
  let filter = $state(false);
  let box = $state<HTMLElement>();

  const shown = $derived.by(() => {
    if (!filter || !value.trim()) return options;
    const q = value.trim().toLowerCase();
    const hits = options.filter((o) => o.toLowerCase().includes(q));
    return hits.length ? hits : options;
  });

  function openList(withFilter: boolean) {
    if (disabled || !options.length) return;
    filter = withFilter;
    open = true;
    active = Math.max(0, shown.indexOf(value));
  }

  function commit(v: string) {
    value = v;
    open = false;
    onchange?.(v);
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) return openList(false);
      const n = shown.length;
      active = (active + (e.key === 'ArrowDown' ? 1 : -1) + n) % n;
      document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter' && open && active >= 0) {
      e.preventDefault();
      e.stopPropagation();
      commit(shown[active]);
    } else if (e.key === 'Escape' && open) {
      e.preventDefault();
      e.stopPropagation();
      open = false;
    } else if (e.key === 'Tab') {
      open = false;
    }
  }

  function onInput() {
    openList(true);
  }

  function onBlur() {
    if (!allowCustom && !options.includes(value)) {
      const m = options.find((o) => o.toLowerCase() === value.trim().toLowerCase());
      value = m ?? options[0] ?? '';
    }
    onchange?.(value);
  }
</script>

<div bind:this={box} class="combo">
  <TextInput
    bind:value
    bind:el
    {id}
    {invalid}
    {placeholder}
    {disabled}
    {size}
    role="combobox"
    aria-label={label}
    aria-describedby={describedby}
    aria-expanded={open}
    aria-controls={listId}
    aria-autocomplete="list"
    aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
    onkeydown={onKeydown}
    oninput={onInput}
    onblur={onBlur}
  >
    {#snippet trailing()}
      <button
        type="button"
        class="chev"
        tabindex="-1"
        aria-label="Show options"
        {disabled}
        onclick={() => (open ? (open = false) : (openList(false), el?.focus()))}
      >
        <Icon name="chevron-down" size={16} />
      </button>
    {/snippet}
  </TextInput>
</div>

{#if open}
  <Popover anchor={box} onclose={() => (open = false)} matchWidth role="none">
    <ul id={listId} role="listbox" aria-label={label} class="opts">
      {#each shown as o, i (o)}
        <li
          id="{listId}-{i}"
          role="option"
          aria-selected={o === value}
          class:active={i === active}
          onpointerdown={(e) => e.preventDefault()}
          onpointermove={() => (active = i)}
          onclick={() => commit(o)}
          onkeydown={() => {}}
        >
          <span>{o}</span>
          {#if o === value}<Icon name="check" size={15} />{/if}
        </li>
      {/each}
    </ul>
  </Popover>
{/if}

<style>
  .combo {
    min-width: 0;
  }
  .chev {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }
  .chev:hover {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
  .opts {
    list-style: none;
    margin: 0;
    padding: 6px;
    max-height: 260px;
    overflow-y: auto;
  }
  li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 9px;
    cursor: pointer;
  }
  li.active {
    background: var(--row-hover);
  }
  li[aria-selected='true'] {
    color: var(--accent-text);
    font-weight: 600;
  }
</style>
