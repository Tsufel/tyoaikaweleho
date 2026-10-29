<script lang="ts">
  import { untrack } from 'svelte';
  import { arc, pie, type PieArcDatum } from 'd3-shape';
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { reduced } from '../lib/motion';
  import { formatDuration, formatMoney } from '../lib/time';
  import { percent, stepIndex, type Slice } from './chartUtils';

  let { slices, label, size = 200 }: { slices: Slice[]; label: string; size?: number } = $props();

  let active = $state<number | null>(null);
  let legend = $state<HTMLElement>();

  const R = $derived(size / 2 - 8);
  const sweep = new Tween(0, { easing: cubicOut });
  const sig = $derived(slices.map((s) => `${s.key}:${s.minutes}`).join('|'));

  $effect(() => {
    void sig;
    untrack(() => {
      void sweep.set(0, { duration: 0 });
      void sweep.set(1, { duration: reduced() ? 0 : 1100 });
    });
  });

  const arcs = $derived.by(() => {
    const end = Math.PI * 2 * sweep.current;
    const gen = pie<Slice>()
      .sort(null)
      .value((s) => s.minutes)
      .startAngle(0)
      .endAngle(Math.max(0.0001, end))
      .padAngle(slices.length > 1 ? 0.025 : 0);
    return gen(slices);
  });

  function path(a: PieArcDatum<Slice>, i: number): string {
    const grow = active === i ? 7 : 0;
    return (
      arc<PieArcDatum<Slice>>()
        .innerRadius(R * 0.66)
        .outerRadius(R + grow)
        .cornerRadius(6)(a) ?? ''
    );
  }

  const fill = (s: Slice) => (s.slot < 0 ? 'var(--series-other)' : `var(--series-${s.slot + 1})`);
  const total = $derived(slices.reduce((t, s) => t + s.minutes, 0));
  const act = $derived(active !== null ? slices[active] ?? null : null);

  function onLegendKey(e: KeyboardEvent, i: number) {
    const k = stepIndex(e.key, i, slices.length, 3);
    if (k === null) return;
    e.preventDefault();
    legend?.querySelectorAll<HTMLElement>('[data-slice]')[k]?.focus();
  }
</script>

<div class="donut">
  <div class="ring" style:width="{size}px" style:height="{size}px">
    <svg width={size} height={size} viewBox="{-size / 2} {-size / 2} {size} {size}" aria-hidden="true">
      <circle class="track" r={R * 0.83} fill="none" stroke-width={R * 0.34} />
      {#each arcs as a, i (a.data.key)}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <path
          d={path(a, i)}
          fill={fill(a.data)}
          class="slice"
          class:dim={active !== null && active !== i}
          onpointerenter={() => (active = i)}
          onpointerleave={() => (active = null)}
        />
      {/each}
    </svg>
    <div class="center" aria-hidden="true">
      {#if act}
        <span class="c-label">{act.label}</span>
        <span class="c-value num">{formatDuration(act.minutes)}</span>
        <span class="c-sub num">{percent(act.share)} · {formatMoney(act.earnings)}</span>
      {:else}
        <span class="c-label">All jobs</span>
        <span class="c-value num">{formatDuration(total)}</span>
        <span class="c-sub">{slices.length} {slices.length === 1 ? 'job' : 'jobs'}</span>
      {/if}
    </div>
  </div>

  <ul class="legend" bind:this={legend} aria-label={label}>
    {#each slices as s, i (s.key)}
      <li>
        <button
          type="button"
          data-slice
          class:on={active === i}
          aria-label="{s.label}: {formatDuration(s.minutes)}, {percent(s.share)}, {formatMoney(s.earnings)}, {s.shifts} {s.shifts === 1 ? 'shift' : 'shifts'}"
          onpointerenter={() => (active = i)}
          onpointerleave={() => (active = null)}
          onfocus={() => (active = i)}
          onblur={() => (active = null)}
          onkeydown={(e) => onLegendKey(e, i)}
        >
          <span class="sw" style:background={fill(s)}></span>
          <span class="name">{s.label}</span>
          <span class="hrs num">{formatDuration(s.minutes)}</span>
          <span class="pct num">{percent(s.share)}</span>
        </button>
      </li>
    {/each}
  </ul>
</div>

<style>
  .donut {
    display: flex;
    align-items: center;
    gap: 22px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .ring {
    position: relative;
    flex: none;
  }
  svg {
    display: block;
    overflow: visible;
  }
  .track {
    stroke: var(--neutral-fill);
  }
  .slice {
    stroke: var(--glass-solid);
    stroke-width: 1;
    transition:
      opacity var(--dur-fast) var(--ease-out),
      filter var(--dur-med) var(--ease-out);
  }
  .slice:hover {
    filter: drop-shadow(0 0 12px var(--chart-glow));
  }
  .slice.dim {
    opacity: 0.4;
  }
  .center {
    position: absolute;
    inset: 22%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    pointer-events: none;
    gap: 1px;
  }
  .c-label {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .c-value {
    font-size: var(--fs-lg);
    font-weight: 700;
    color: var(--text);
  }
  .c-sub {
    font-size: var(--fs-xs);
    color: var(--text-subtle);
  }
  .legend {
    list-style: none;
    margin: 0;
    padding: 0;
    flex: 1 1 200px;
    min-width: 0;
    display: grid;
    gap: 2px;
  }
  .legend button {
    width: 100%;
    display: grid;
    grid-template-columns: 12px 1fr auto 3.2em;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text);
    font-size: var(--fs-sm);
    text-align: left;
    cursor: default;
    transition: background var(--dur-fast);
  }
  .legend button:hover,
  .legend button.on {
    background: var(--row-hover);
  }
  .legend button:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
  }
  .sw {
    width: 12px;
    height: 12px;
    border-radius: 4px;
    box-shadow: 0 0 0 2px var(--glass-solid);
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .hrs {
    color: var(--text-muted);
  }
  .pct {
    color: var(--text);
    font-weight: 650;
    text-align: right;
  }
</style>
