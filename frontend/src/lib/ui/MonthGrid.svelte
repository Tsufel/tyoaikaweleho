<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { MONTHS_SHORT } from '../time';
  import Icon from './Icon.svelte';

  /** Year header + 12-month grid (used by views/entries/MonthPicker and the
   *  top-bar month button). Arrows move, PgUp/PgDn change year, Enter picks. */
  let {
    year,
    month,
    onpick,
  }: { year: number; month: number; onpick: (year: number, month: number) => void } = $props();

  const now = new Date();
  const init = () => ({ y: year, m: month });
  let y = $state(init().y);
  let cur = $state(init().m);
  let grid = $state<HTMLElement>();

  function focusCur() {
    void tick().then(() => grid?.querySelector<HTMLElement>('[tabindex="0"]')?.focus());
  }

  function move(d: number) {
    let m = cur + d;
    while (m < 1) {
      m += 12;
      y -= 1;
    }
    while (m > 12) {
      m -= 12;
      y += 1;
    }
    cur = m;
    focusCur();
  }

  function onKeydown(e: KeyboardEvent) {
    const k = e.key;
    if (k === 'ArrowLeft') move(-1);
    else if (k === 'ArrowRight') move(1);
    else if (k === 'ArrowUp') move(-3);
    else if (k === 'ArrowDown') move(3);
    else if (k === 'PageUp') move(-12);
    else if (k === 'PageDown') move(12);
    else if (k === 'Enter' || k === ' ') onpick(y, cur);
    else return;
    e.preventDefault();
    e.stopPropagation();
  }

  onMount(focusCur);
</script>

<div class="mg">
  <div class="head">
    <button type="button" class="nav" aria-label="Previous year" onclick={() => (y -= 1)}>
      <Icon name="chevron-left" size={16} />
    </button>
    <span class="title" aria-live="polite">{y}</span>
    <button type="button" class="nav" aria-label="Next year" onclick={() => (y += 1)}>
      <Icon name="chevron-right" size={16} />
    </button>
  </div>
  <div bind:this={grid} class="grid" role="grid" aria-label="Months of {y}" tabindex="-1" onkeydown={onKeydown}>
    {#each [0, 1, 2, 3] as r (r)}
      <div class="row" role="row">
        {#each [1, 2, 3] as c (c)}
          {@const m = r * 3 + c}
          <button
            type="button"
            role="gridcell"
            class:selected={y === year && m === month}
            class:current={y === now.getFullYear() && m === now.getMonth() + 1}
            aria-selected={y === year && m === month}
            tabindex={m === cur ? 0 : -1}
            onclick={() => onpick(y, m)}
          >
            {MONTHS_SHORT[m - 1]}
          </button>
        {/each}
      </div>
    {/each}
  </div>
</div>

<style>
  .mg {
    padding: 10px;
    width: 250px;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .title {
    font-weight: 650;
    font-family: var(--font-mono);
  }
  .nav {
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
  .nav:hover {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
  .grid {
    display: flex;
    flex-direction: column;
    gap: 4px;
    outline: none;
  }
  .row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
  }
  .row button {
    height: 38px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    font-weight: 600;
    cursor: pointer;
  }
  .row button:hover {
    background: var(--row-hover);
  }
  .current {
    box-shadow: inset 0 0 0 1.5px var(--accent);
  }
  .selected,
  .selected:hover {
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    color: var(--on-accent);
  }
</style>
