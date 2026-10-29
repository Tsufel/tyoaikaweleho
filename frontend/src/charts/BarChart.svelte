<script lang="ts">
  import { scaleBand } from 'd3-scale';
  import { untrack } from 'svelte';
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import type { StatsBucket } from '../lib/api/types';
  import { reduced } from '../lib/motion';
  import { formatDuration, formatMoney } from '../lib/time';
  import ChartTooltip from './ChartTooltip.svelte';
  import { axisHours, barPath, hourScale, labelStep, resize, stepIndex } from './chartUtils';

  let {
    buckets,
    targets,
    label,
    onopen,
    height = 260,
  }: {
    buckets: StatsBucket[];
    /** Target hours per bucket (same length as buckets). */
    targets: number[];
    label: string;
    onopen?: (b: StatsBucket) => void;
    height?: number;
  } = $props();

  const uid = $props.id();
  const M = { top: 16, right: 14, bottom: 30, left: 46 };

  let width = $state(0);
  let active = $state<number | null>(null);
  let focused = $state(false);

  const hours = $derived(buckets.map((b) => b.minutes / 60));
  const plotW = $derived(Math.max(0, width - M.left - M.right));
  const plotH = $derived(height - M.top - M.bottom);
  const maxTarget = $derived(targets.length ? Math.max(...targets) : 0);
  const scale = $derived(hourScale(Math.max(0, ...hours), maxTarget, plotH));
  const x = $derived(
    scaleBand<number>()
      .domain(buckets.map((_, i) => i))
      .range([0, plotW])
      .paddingInner(buckets.length > 40 ? 0.18 : 0.28)
      .paddingOuter(0.12),
  );
  const step = $derived(labelStep(buckets.length, plotW, 46));
  const flatTarget = $derived(targets.length > 0 && targets.every((t) => t === targets[0]) ? targets[0] : null);

  // Grow from the previous values with a left-to-right stagger.
  let from: number[] = [];
  let to = $state<number[]>([]);
  const progress = new Tween(1, { easing: cubicOut });

  $effect(() => {
    const next = hours;
    untrack(() => {
      const p = progress.current;
      from = resize(
        to.map((v, i) => shown(i, p, v)),
        next.length,
      );
      to = next;
      void progress.set(0, { duration: 0 });
      void progress.set(1, { duration: reduced() ? 0 : 900 });
    });
  });

  const STAGGER = 0.55;
  function shown(i: number, p: number, target: number): number {
    const start = from[i] ?? 0;
    const n = Math.max(1, to.length);
    const local = Math.max(0, Math.min(1, (p * (1 + STAGGER) - (i / n) * STAGGER)));
    const k = 1 - Math.pow(1 - local, 3);
    return start + (target - start) * k;
  }

  const bars = $derived(
    to.map((v, i) => {
      const h = shown(i, progress.current, v);
      const bx = x(i) ?? 0;
      const y = scale.y(h);
      return { i, x: bx, w: x.bandwidth(), y, d: barPath(bx, y, x.bandwidth(), plotH - y, 5) };
    }),
  );

  function pick(e: PointerEvent) {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const px = e.clientX - r.left - M.left;
    if (px < 0 || px > plotW || !buckets.length) {
      active = null;
      return;
    }
    const i = Math.floor((px / plotW) * buckets.length);
    active = Math.max(0, Math.min(buckets.length - 1, i));
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && active !== null && onopen) {
      e.preventDefault();
      onopen(buckets[active]);
      return;
    }
    if (e.key === 'Escape' && active !== null) {
      e.stopPropagation();
      active = null;
      return;
    }
    const n = stepIndex(e.key, active, buckets.length);
    if (n === null) return;
    e.preventDefault();
    active = n;
  }

  const act = $derived(active !== null && active < buckets.length ? buckets[active] : null);
  const actTarget = $derived(active !== null ? (targets[active] ?? 0) : 0);
  const announce = $derived(
    act
      ? `${act.label}: ${formatDuration(act.minutes)}, ${formatMoney(act.earnings)}, ${act.shifts} ${act.shifts === 1 ? 'shift' : 'shifts'}${actTarget > 0 ? `, target ${axisHours(actTarget)}` : ''}`
      : '',
  );
</script>

<div class="chart" bind:clientWidth={width} style:height="{height}px">
  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
  <div
    class="focus-box"
    role="group"
    tabindex="0"
    aria-label="{label}. Use the arrow keys to read each bar{onopen ? ', Enter to open the shifts' : ''}."
    aria-roledescription="bar chart"
    class:clickable={!!onopen && act}
    {onkeydown}
    onpointermove={pick}
    onpointerleave={() => {
      if (!focused) active = null;
    }}
    onclick={() => act && onopen?.(act)}
    onfocus={() => {
      focused = true;
      if (active === null && buckets.length) active = buckets.length - 1;
    }}
    onblur={() => {
      focused = false;
      active = null;
    }}
  >
    {#if width > 0}
      <svg {width} {height} aria-hidden="true">
        <defs>
          <linearGradient id="{uid}-bar" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stop-color="var(--chart-bar-a)" />
            <stop offset="100%" stop-color="var(--chart-bar-b)" />
          </linearGradient>
          <linearGradient id="{uid}-bar-hot" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stop-color="var(--chart-bar-a)" />
            <stop offset="100%" stop-color="var(--chart-bar-hot)" />
          </linearGradient>
        </defs>
        <g transform="translate({M.left},{M.top})">
          {#each scale.ticks as t (t)}
            <line class="grid" x1="0" x2={plotW} y1={scale.y(t)} y2={scale.y(t)} />
            <text class="axis" x="-10" y={scale.y(t)} dy="0.32em" text-anchor="end">{axisHours(t)}</text>
          {/each}

          {#each bars as b (b.i)}
            {#if b.d}
              <path
                d={b.d}
                fill="url(#{uid}-{targets[b.i] > 0 && hours[b.i] >= targets[b.i] ? 'bar-hot' : 'bar'})"
                class="bar"
                class:dim={active !== null && active !== b.i}
                class:on={active === b.i}
              />
            {/if}
            {#if flatTarget === null && targets[b.i] > 0}
              <line
                class="target tick"
                x1={b.x - 2}
                x2={b.x + b.w + 2}
                y1={scale.y(targets[b.i])}
                y2={scale.y(targets[b.i])}
              />
            {/if}
          {/each}

          {#if flatTarget !== null && flatTarget > 0}
            <line class="target" x1="0" x2={plotW} y1={scale.y(flatTarget)} y2={scale.y(flatTarget)} />
            <text class="target-label" x={plotW} y={scale.y(flatTarget) - 6} text-anchor="end">Target {axisHours(flatTarget)}</text>
          {/if}

          <line class="baseline" x1="0" x2={plotW} y1={plotH} y2={plotH} />

          {#each buckets as b, i (b.key)}
            {#if i % step === 0 || i === active}
              <text
                class="axis"
                class:axis-on={i === active}
                x={(x(i) ?? 0) + x.bandwidth() / 2}
                y={plotH + 19}
                text-anchor="middle">{b.label}</text
              >
            {/if}
          {/each}
        </g>
      </svg>

      {#if act && active !== null}
        <ChartTooltip x={M.left + (x(active) ?? 0) + x.bandwidth() / 2} y={M.top + (bars[active]?.y ?? plotH)} {width}>
          <div class="t-title">{act.label}</div>
          <div class="t-row">Hours <b>{formatDuration(act.minutes)}</b></div>
          <div class="t-row">Earnings <b>{formatMoney(act.earnings)}</b></div>
          <div class="t-row">Shifts <b>{act.shifts}</b></div>
          {#if actTarget > 0}
            <div class="t-row">
              Target <b>{axisHours(actTarget)}{act.minutes / 60 >= actTarget ? ' ✓' : ''}</b>
            </div>
          {/if}
        </ChartTooltip>
      {/if}
    {/if}
  </div>
  <div class="sr-only" aria-live="polite">{announce}</div>
</div>

<style>
  .chart {
    position: relative;
    width: 100%;
  }
  .focus-box {
    position: relative;
    height: 100%;
    border-radius: var(--radius-md);
    outline: none;
  }
  .focus-box:focus-visible {
    box-shadow: 0 0 0 2px var(--focus-ring);
  }
  svg {
    display: block;
    overflow: visible;
  }
  .clickable {
    cursor: pointer;
  }
  .grid {
    stroke: var(--divider);
    stroke-width: 1;
  }
  .baseline {
    stroke: var(--glass-border);
    stroke-width: 1;
  }
  .axis {
    fill: var(--text-subtle);
    font-size: 11px;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }
  .axis-on {
    fill: var(--text);
    font-weight: 650;
  }
  .bar {
    transition:
      opacity var(--dur-fast) var(--ease-out),
      filter var(--dur-med) var(--ease-out);
  }
  .bar.dim {
    opacity: 0.45;
  }
  .bar.on {
    filter: drop-shadow(0 0 10px var(--chart-glow));
  }
  .target {
    stroke: var(--chart-target);
    stroke-width: 1.5;
    stroke-dasharray: 5 5;
  }
  .target.tick {
    stroke-dasharray: 3 3;
    stroke-width: 2;
  }
  .target-label {
    fill: var(--chart-target-text);
    font-size: 11px;
    font-weight: 650;
    paint-order: stroke;
    stroke: var(--glass-solid);
    stroke-width: 3px;
    stroke-linejoin: round;
  }
</style>
