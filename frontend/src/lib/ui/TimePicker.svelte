<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { SLOTS, nearestSlot } from '../time';

  /** 48 half-hour slots (v1.3 ui/time_picker_popup): the slot nearest to
   *  `value` is highlighted and centred; ↑/↓/PgUp/PgDn/Home/End move,
   *  Enter picks, Escape cancels (handled by the surrounding Popover). */
  let {
    value = null,
    onpick,
    label = 'Pick a time',
  }: { value?: string | null; onpick: (t: string) => void; label?: string } = $props();

  const listId = `tp-${Math.random().toString(36).slice(2, 8)}`;
  const initial = () => nearestSlot(value) ?? 18;
  let active = $state(initial());
  let list = $state<HTMLUListElement>();

  function scrollTo(i: number, center = false) {
    const li = list?.children[i] as HTMLElement | undefined;
    if (!li || !list) return;
    if (center) list.scrollTop = li.offsetTop - list.clientHeight / 2 + li.offsetHeight / 2;
    else li.scrollIntoView({ block: 'nearest' });
  }

  function move(i: number) {
    active = Math.min(SLOTS.length - 1, Math.max(0, i));
    scrollTo(active);
  }

  function onKeydown(e: KeyboardEvent) {
    const k = e.key;
    if (k === 'ArrowDown') move(active + 1);
    else if (k === 'ArrowUp') move(active - 1);
    else if (k === 'PageDown') move(active + 8);
    else if (k === 'PageUp') move(active - 8);
    else if (k === 'Home') move(0);
    else if (k === 'End') move(SLOTS.length - 1);
    else if (k === 'Enter' || k === ' ') onpick(SLOTS[active]);
    else return;
    e.preventDefault();
    e.stopPropagation();
  }

  onMount(() => {
    void tick().then(() => {
      scrollTo(active, true);
      list?.focus();
    });
  });
</script>

<ul
  bind:this={list}
  id={listId}
  class="slots"
  role="listbox"
  tabindex="0"
  aria-label={label}
  aria-activedescendant="{listId}-{active}"
  onkeydown={onKeydown}
>
  {#each SLOTS as s, i (s)}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <li
      id="{listId}-{i}"
      role="option"
      aria-selected={i === active}
      class:active={i === active}
      class:hour={i % 2 === 0}
      onpointermove={() => (active = i)}
      onclick={() => onpick(s)}
    >
      {s}
    </li>
  {/each}
</ul>

<style>
  .slots {
    list-style: none;
    margin: 0;
    padding: 6px;
    width: 116px;
    max-height: 288px;
    overflow-y: auto;
    outline: none;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }
  li {
    padding: 7px 12px;
    border-radius: 9px;
    font-size: var(--fs-md);
    color: var(--text-muted);
    cursor: pointer;
    text-align: center;
  }
  li.hour {
    color: var(--text);
  }
  li.active {
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    color: var(--on-accent);
  }
  .slots:focus-visible {
    box-shadow: inset 0 0 0 2px var(--focus-ring);
    border-radius: var(--radius-md);
  }
</style>
