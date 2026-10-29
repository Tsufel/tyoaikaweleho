<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { MONTHS, WEEKDAYS_MIN, fromIsoDate, toIsoDate } from '../time';
  import Icon from './Icon.svelte';

  /** Monday-first month grid. Arrows move by day/week, PgUp/PgDn by month,
   *  Home/End to week start/end, Enter picks. */
  let {
    value = null,
    onpick,
    autofocus = true,
  }: { value?: string | null; onpick: (iso: string) => void; autofocus?: boolean } = $props();

  const today = toIsoDate(new Date());
  const start = (() => fromIsoDate(value ?? '') ?? new Date())();
  let cursor = $state(new Date(start.getFullYear(), start.getMonth(), start.getDate()));
  let grid = $state<HTMLElement>();

  const year = $derived(cursor.getFullYear());
  const month = $derived(cursor.getMonth());
  const cursorIso = $derived(toIsoDate(cursor));

  const days = $derived.by(() => {
    const first = new Date(year, month, 1);
    const lead = (first.getDay() + 6) % 7;
    const out: { iso: string; day: number; inMonth: boolean }[] = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(year, month, 1 - lead + i);
      out.push({ iso: toIsoDate(d), day: d.getDate(), inMonth: d.getMonth() === month });
    }
    return out;
  });

  function setCursor(d: Date) {
    cursor = d;
    void tick().then(() => grid?.querySelector<HTMLElement>('[data-cursor="true"]')?.focus());
  }

  function addDays(n: number) {
    setCursor(new Date(year, month, cursor.getDate() + n));
  }

  function addMonth(n: number) {
    const last = new Date(year, month + n + 1, 0).getDate();
    setCursor(new Date(year, month + n, Math.min(cursor.getDate(), last)));
  }

  function onKeydown(e: KeyboardEvent) {
    const k = e.key;
    if (k === 'ArrowLeft') addDays(-1);
    else if (k === 'ArrowRight') addDays(1);
    else if (k === 'ArrowUp') addDays(-7);
    else if (k === 'ArrowDown') addDays(7);
    else if (k === 'PageUp') addMonth(e.shiftKey ? -12 : -1);
    else if (k === 'PageDown') addMonth(e.shiftKey ? 12 : 1);
    else if (k === 'Home') addDays(-((cursor.getDay() + 6) % 7));
    else if (k === 'End') addDays(6 - ((cursor.getDay() + 6) % 7));
    else if (k === 'Enter' || k === ' ') onpick(cursorIso);
    else return;
    e.preventDefault();
    e.stopPropagation();
  }

  onMount(() => {
    if (autofocus) void tick().then(() => grid?.querySelector<HTMLElement>('[data-cursor="true"]')?.focus());
  });
</script>

<div class="cal">
  <div class="head">
    <button type="button" class="nav" aria-label="Previous month" onclick={() => addMonth(-1)}>
      <Icon name="chevron-left" size={16} />
    </button>
    <span class="title" aria-live="polite">{MONTHS[month]} {year}</span>
    <button type="button" class="nav" aria-label="Next month" onclick={() => addMonth(1)}>
      <Icon name="chevron-right" size={16} />
    </button>
  </div>
  <div bind:this={grid} class="grid" role="grid" aria-label="{MONTHS[month]} {year}" tabindex="-1" onkeydown={onKeydown}>
    <div class="row" role="row">
      {#each WEEKDAYS_MIN as w (w)}<span class="wd" role="columnheader">{w}</span>{/each}
    </div>
    {#each [0, 1, 2, 3, 4, 5] as r (r)}
      <div class="row" role="row">
        {#each days.slice(r * 7, r * 7 + 7) as d (d.iso)}
          <button
            type="button"
            role="gridcell"
            class="day"
            class:out={!d.inMonth}
            class:today={d.iso === today}
            class:selected={d.iso === value}
            aria-selected={d.iso === value}
            aria-current={d.iso === today ? 'date' : undefined}
            aria-label={d.iso}
            data-cursor={d.iso === cursorIso}
            tabindex={d.iso === cursorIso ? 0 : -1}
            onclick={() => onpick(d.iso)}
          >
            {d.day}
          </button>
        {/each}
      </div>
    {/each}
  </div>
</div>

<style>
  .cal {
    padding: 10px;
    width: 280px;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .title {
    font-weight: 650;
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
    outline: none;
  }
  .row {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
  }
  .wd {
    text-align: center;
    font-size: var(--fs-xs);
    color: var(--text-muted);
    padding: 4px 0;
  }
  .day {
    height: 34px;
    border: 0;
    border-radius: 9px;
    background: transparent;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: var(--fs-sm);
    cursor: pointer;
  }
  .day:hover {
    background: var(--row-hover);
  }
  .out {
    color: var(--text-subtle);
  }
  .today {
    box-shadow: inset 0 0 0 1.5px var(--accent);
  }
  .selected {
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    color: var(--on-accent);
  }
  .selected:hover {
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
  }
</style>
