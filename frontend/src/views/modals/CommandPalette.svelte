<script lang="ts">
  import { tick } from 'svelte';
  import type { CommandName } from '../../lib/api/types';
  import { availableItems, filterItems, itemKeys } from '../../lib/commandPalette';
  import { runCommand } from '../../lib/shortcuts';
  import Kbd from '../../lib/ui/Kbd.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  /** Ctrl+K: find a command by name and run it. Esc closes. */
  let { onclose }: { onclose: () => void } = $props();

  const uid = Math.random().toString(36).slice(2, 8);
  const listId = `palette-list-${uid}`;
  // what can run is fixed while the palette is up (it owns the keyboard)
  const items = availableItems();
  let query = $state('');
  let active = $state(0);
  let listEl = $state<HTMLUListElement>();
  const shown = $derived(filterItems(items, query));
  const optId = (i: number) => `palette-opt-${uid}-${i}`;

  $effect(() => {
    // a new query starts from the best match
    void query;
    active = 0;
  });
  $effect(() => {
    listEl?.querySelector(`#${optId(active)}`)?.scrollIntoView({ block: 'nearest' });
  });

  async function run(cmd: CommandName) {
    onclose();
    // after the palette is gone, so a command can open its own dialog
    await tick();
    runCommand(cmd);
  }

  function onKeydown(e: KeyboardEvent) {
    const n = shown.length;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (n) active = (active + (e.key === 'ArrowDown' ? 1 : -1) + n) % n;
    } else if ((e.key === 'PageDown' || e.key === 'PageUp') && n) {
      e.preventDefault();
      active = e.key === 'PageDown' ? n - 1 : 0;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const it = shown[active];
      if (it) void run(it.cmd);
    }
  }
</script>

<Modal title="Commands" size="sm" {onclose} initialFocus="[data-palette-input]" class="palette">
  <input
    data-palette-input
    class="search"
    type="text"
    role="combobox"
    aria-label="Find a command"
    aria-autocomplete="list"
    aria-expanded="true"
    aria-controls={listId}
    aria-activedescendant={shown.length ? optId(active) : undefined}
    placeholder="Type a command…"
    autocomplete="off"
    spellcheck="false"
    bind:value={query}
    onkeydown={onKeydown}
  />
  <ul id={listId} class="list" role="listbox" aria-label="Commands" bind:this={listEl}>
    {#each shown as it, i (it.cmd)}
      {@const keys = itemKeys(it)}
      <!-- the combobox owns focus and keys; a click runs the option -->
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <li
        id={optId(i)}
        role="option"
        aria-selected={i === active}
        class:active={i === active}
        onpointermove={() => (active = i)}
        onclick={() => void run(it.cmd)}
      >
        <span class="label">{it.label}</span>
        {#if keys}<Kbd {keys} />{/if}
      </li>
    {/each}
  </ul>
  {#if !shown.length}
    <p class="empty" role="status">No command matches “{query.trim()}”.</p>
  {/if}
</Modal>

<style>
  .search {
    width: 100%;
    height: 38px;
    padding: 0 12px;
    border-radius: var(--radius-md);
    border: 1px solid var(--field-border);
    background: var(--field-bg);
    color: var(--text);
    font: inherit;
    outline: none;
  }
  .search:focus {
    background: var(--field-bg-focus);
    box-shadow: var(--focus-ring);
  }
  .list {
    list-style: none;
    margin: 10px 0 0;
    padding: 0;
    max-height: min(360px, 50vh);
    overflow: auto;
  }
  li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    color: var(--text);
  }
  li.active {
    background: var(--row-selected);
  }
  .label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .empty {
    margin: 12px 4px 4px;
    color: var(--text-muted);
  }
</style>
