<script lang="ts">
  import { untrack } from 'svelte';
  import { scaleLinear } from 'd3-scale';
  import { area, curveMonotoneX, line } from 'd3-shape';
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import type { StatsBucket } from '../lib/api/types';
  import { reduced } from '../lib/motion';
  import { formatDuration, formatMoney } from '../lib/time';
  import ChartTooltip from './ChartTooltip.svelte';
  import { axisMoney, cumulative, labelStep, moneyScale, resize, stepIndex } from './chartUtils';

  /** Running total of earnings across the range. */
  let { buckets, label, height = 220 }: { buckets: StatsBucket[]; label: string; height?: number } = $props();

  const uid = $props.id();
  const M = { top: 18, right: 18, bottom: 30, left: 54 };

  let width = $state(0);
  let active = $state<number | null>(null);
  let focused = $state(false);

  const totals = $derived(cumulative(buckets.map((b) => b.earnings)));
  const plotW = $derived(Math.max(0, width - M.left - M.right));
  const plotH = $derived(height - M.top - M.bottom);
  const scale = $derived(moneyScale(totals.at(-1) ?? 0, plotH));
  const n = $derived(buckets.length);
  const xAt = $derived((i: number) => (n <= 1 ? plotW / 2 : scaleLinear().domain([0, n - 1]).range([0, plotW])(i)));
  const step = $derived(labelStep(n, plotW, 52));

  const tween = new Tween<number[]>([], { easing: cubicOut });
  $effect(() => {
    const next = totals;
    untrack(() => {
      if (tween.current.length !== next.length) void tween.set(resize([], next.length), { duration: 0 });
      void tween.set(next, { duration: reduced() ? 0 : 1000 });
    });
  });

  const pts = $derived(tween.current.map((v, i) => [xAt(i), scale.y(v)] as [number, number]));
  const areaD = $derived(
    area<[number, number]>()
      .x((p) => p[0])
      .y0(plotH)
      .y1((p) => p[1])
      .curve(curveMonotoneX)(pts) ?? '',
  );
  const lineD = $derived(
    line<[number, number]>()
      .x((p) => p[0])
      .y((p) => p[1])
      .curve(curveMonotoneX)(pts) ?? '',
  );
  const last = $derived(pts.at(-1));

  function pick(e: PointerEvent) {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const px = e.clientX - r.left - M.left;
    if (px < -12 || px > plotW + 12 || !n) {
      active = null;
      return;
    }
    active = n <= 1 ? 0 : Math.max(0, Math.min(n - 1, Math.round((px / plotW) * (n - 1))));
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && active !== null) {
      e.stopPropagation();
      active = null;
      return;
    }
    const k = stepIndex(e.key, active, n);
    if (k === null) return;
    e.preventDefault();
    active = k;
  }

  const act = $derived(active !== null && active < n ? buckets[active] : null);
  const announce = $derived(
    act && active !== null ? `${act.label}: ${formatMoney(act.earnings)}, running total ${formatMoney(totals[active])}` : '',
  );
</script>

<div class="chart" bind:clientWidth={width} style:height="{height}px">
  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
  <div
    class="focus-box"
    role="group"
    tabindex="0"
    aria-label="{label}. Use the arrow keys to read each point."
    aria-roledescription="area chart"
    {onkeydown}
    onpointermove={pick}
    onpointerleave={() => {
      if (!focused) active = null;
    }}
    onfocus={() => {
      focused = true;
      if (active === null && n) active = n - 1;
    }}
    onblur={() => {
      focused = false;
      active = null;
    }}
  >
    {#if width > 0}
      <svg {width} {height} aria-hidden="true">
        <defs>
          <linearGradient id="{uid}-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--chart-area)" stop-opacity="0.42" />
            <stop offset="100%" stop-color="var(--chart-area)" stop-opacity="0" />
          </linearGradient>
          <linearGradient id="{uid}-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="var(--chart-line-a)" />
            <stop offset="100%" stop-color="var(--chart-line-b)" />
          </linearGradient>
        </defs>
        <g transform="translate({M.left},{M.top})">
          {#each scale.ticks as t (t)}
            <line class="grid" x1="0" x2={plotW} y1={scale.y(t)} y2={scale.y(t)} />
            <text class="axis" x="-10" y={scale.y(t)} dy="0.32em" text-anchor="end">{axisMoney(t)}</text>
          {/each}
          <line class="baseline" x1="0" x2={plotW} y1={plotH} y2={plotH} />

          {#if n > 1}
            <path d={areaD} fill="url(#{uid}-fill)" />
            <path d={lineD} class="line" stroke="url(#{uid}-line)" />
          {/if}

          {#if act && active !== null && pts[active]}
            <line class="cross" x1={pts[active][0]} x2={pts[active][0]} y1="0" y2={plotH} />
            <circle class="dot" cx={pts[active][0]} cy={pts[active][1]} r="5" />
          {:else if last}
            <circle class="dot end" cx={last[0]} cy={last[1]} r="4" />
            <text class="end-label" x={last[0] - 8} y={last[1] - 10} text-anchor={n > 1 ? 'end' : 'middle'}>
              {formatMoney(totals.at(-1) ?? 0)}
            </text>
          {/if}

          {#each buckets as b, i (b.key)}
            {#if i % step === 0 || i === active}
              <text class="axis" class:axis-on={i === active} x={xAt(i)} y={plotH + 19} text-anchor="middle">{b.label}</text>
            {/if}
          {/each}
        </g>
      </svg>

      {#if act && active !== null && pts[active]}
        <ChartTooltip x={M.left + pts[active][0]} y={M.top + pts[active][1]} {width}>
          <div class="t-title">{act.label}</div>
          <div class="t-row">Earned <b>{formatMoney(act.earnings)}</b></div>
          <div class="t-row">Running total <b>{formatMoney(totals[active])}</b></div>
          <div class="t-row">Hours <b>{formatDuration(act.minutes)}</b></div>
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
  .grid {
    stroke: var(--divider);
  }
  .baseline {
    stroke: var(--glass-border);
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
  .line {
    fill: none;
    stroke-width: 2.5;
    stroke-linecap: round;
    filter: drop-shadow(0 2px 8px var(--chart-glow-2));
  }
  .cross {
    stroke: var(--text-subtle);
    stroke-dasharray: 3 4;
  }
  .dot {
    fill: var(--chart-line-b);
    stroke: var(--glass-solid);
    stroke-width: 2.5;
    filter: drop-shadow(0 0 8px var(--chart-glow-2));
  }
  .end-label {
    fill: var(--text);
    font-size: 12px;
    font-weight: 650;
    font-family: var(--font-mono);
    paint-order: stroke;
    stroke: var(--glass-solid);
    stroke-width: 4px;
    stroke-linejoin: round;
  }
</style>
