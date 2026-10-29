<script lang="ts" module>
  import type { IconName } from './Icon.svelte';

  export interface MenuItem {
    id: string;
    label: string;
    icon?: IconName;
    kbd?: string;
    danger?: boolean;
    disabled?: boolean;
    /** Draw a divider above this item. */
    separator?: boolean;
  }
</script>

<script lang="ts">
  import { onMount, tick } from 'svelte';
  import Icon from './Icon.svelte';
  import Popover from './Popover.svelte';

  /** Dropdown menu; mount with {#if open}. ↑/↓/Home/End move, Enter picks,
   *  Esc closes and returns focus to the anchor. */
  let {
    anchor,
    items,
    onselect,
    onclose,
    label = 'Menu',
    placement = 'bottom-end',
  }: {
    anchor: HTMLElement | null | undefined;
    items: MenuItem[];
    onselect: (id: string) => void;
    onclose: () => void;
    label?: string;
    placement?: 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end';
  } = $props();

  let list = $state<HTMLElement>();

  const buttons = () => [...(list?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]:not(:disabled)') ?? [])];

  function onKeydown(e: KeyboardEvent) {
    const all = buttons();
    const i = all.indexOf(document.activeElement as HTMLButtonElement);
    let n: number;
    if (e.key === 'ArrowDown') n = (i + 1) % all.length;
    else if (e.key === 'ArrowUp') n = (i - 1 + all.length) % all.length;
    else if (e.key === 'Home') n = 0;
    else if (e.key === 'End') n = all.length - 1;
    else if (e.key === 'Tab') {
      e.preventDefault();
      onclose();
      anchor?.focus();
      return;
    } else return;
    e.preventDefault();
    all[n]?.focus();
  }

  function pick(it: MenuItem) {
    onclose();
    anchor?.focus();
    onselect(it.id);
  }

  onMount(() => {
    void tick().then(() => buttons()[0]?.focus());
  });
</script>

<Popover {anchor} {onclose} {placement} role="none">
  <div bind:this={list} class="menu" role="menu" aria-label={label} tabindex="-1" onkeydown={onKeydown}>
    {#each items as it (it.id)}
      {#if it.separator}<div class="sep" role="separator"></div>{/if}
      <button type="button" role="menuitem" class:danger={it.danger} disabled={it.disabled} onclick={() => pick(it)}>
        {#if it.icon}<Icon name={it.icon} size={16} />{/if}
        <span class="lbl">{it.label}</span>
        {#if it.kbd}<span class="kbd">{it.kbd}</span>{/if}
      </button>
    {/each}
  </div>
</Popover>

<style>
  .menu {
    display: flex;
    flex-direction: column;
    min-width: 200px;
    padding: 6px;
    outline: none;
  }
  button {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: 0;
    border-radius: 9px;
    background: transparent;
    text-align: left;
    font-size: var(--fs-sm);
    cursor: pointer;
  }
  button:hover,
  button:focus-visible {
    background: var(--row-hover);
    outline: none;
  }
  button:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .danger {
    color: var(--danger-text);
  }
  .lbl {
    flex: 1;
  }
  .kbd {
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .sep {
    height: 1px;
    margin: 4px 6px;
    background: var(--divider);
  }
</style>
