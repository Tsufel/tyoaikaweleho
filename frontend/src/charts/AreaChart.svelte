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
  import { axisMoney, labelStep, moneyScale, paceAt, resize, stepIndex, type EarningsModel } from './chartUtils';

  /**
   * Running total of earnings across the range. The line stops at
   * `model.elapsed` (days ahead are not earned yet); a dashed line runs on to
   * `model.projected`, and the previous period is drawn faintly behind.
   */
  let {
    buckets,
    model,
    previousName = 'Before',
    label,
    height = 220,
  }: { buckets: StatsBucket[]; model: EarningsModel; previousName?: string; label: string; height?: number } =
    $props();

  const uid = $props.id();
  const M = { top: 18, right: 18, bottom: 30, left: 54 };

  let width = $state(0);
  let active = $state<number | null>(null);
  let focused = $state(false);

  const n = $derived(buckets.length);
  const totals = $derived(model.totals);
  const elapsed = $derived(Math.min(model.elapsed, n - 1));
  const sofar = $derived(elapsed >= 0 ? (totals[elapsed] ?? 0) : 0);
  const projected = $derived(elapsed < n - 1 ? model.projected : null);
  const previous = $derived(model.previous && model.previous.length === n ? model.previous : null);

  const plotW = $derived(Math.max(0, width - M.left - M.right));
  const plotH = $derived(height - M.top - M.bottom);
  const target = $derived(Math.max(sofar, projected ?? 0, previous ? Math.max(...previous) : 0));
  const xAt = $derived((i: number) => (n <= 1 ? plotW / 2 : scaleLinear().domain([0, n - 1]).range([0, plotW])(i)));
  const step = $derived(labelStep(n, plotW, 52));

  // one tween for every series: [running total × n, previous × n, projection]
  const tween = new Tween<number[]>([], { easing: cubicOut });
  $effect(() => {
    const next = [...totals, ...(previous ?? totals.map(() => 0)), projected ?? sofar];
    untrack(() => {
      if (tween.current.length !== next.length) void tween.set(resize([], next.length), { duration: 0 });
      void tween.set(next, { duration: reduced() ? 0 : 1000 });
    });
  });
  const tv = $derived(tween.current.length === 2 * n + 1 ? tween.current : [...totals, ...totals.map(() => 0), sofar]);
  // while values tween down the scale keeps their old top, so no line is drawn above the plot
  const scale = $derived(moneyScale(Math.max(target, ...tv), plotH));

  const earnedPts = $derived(
    elapsed < 0 ? [] : tv.slice(0, elapsed + 1).map((v, i) => [xAt(i), scale.y(v)] as [number, number]),
  );
  const prevPts = $derived(previous ? tv.slice(n, 2 * n).map((v, i) => [xAt(i), scale.y(v)] as [number, number]) : []);
  const paceFrom = $derived(earnedPts.at(-1));
  const paceTo = $derived(projected !== null && paceFrom ? ([xAt(n - 1), scale.y(tv[2 * n])] as [number, number]) : null);

  const areaD = $derived(
    area<[number, number]>()
      .x((p) => p[0])
      .y0(plotH)
      .y1((p) => p[1])
      .curve(curveMonotoneX)(earnedPts) ?? '',
  );
  const lineOf = (pts: [number, number][]) =>
    line<[number, number]>()
      .x((p) => p[0])
      .y((p) => p[1])
      .curve(curveMonotoneX)(pts) ?? '';
  const lineD = $derived(lineOf(earnedPts));
  const prevD = $derived(lineOf(prevPts));

  /** Room for the pace label beside the end-of-today label. */
  const paceLabel = $derived(!!(paceTo && paceFrom && paceTo[0] - paceFrom[0] >= 96));

  /** Where the tooltip points: earned, then the pace line, then last period's line. */
  function anchor(i: number): [number, number] {
    if (i <= elapsed && earnedPts[i]) return earnedPts[i];
    if (projected !== null) return [xAt(i), scale.y(paceAt(i, elapsed, n, tv[elapsed] ?? 0, tv[2 * n]))];
    if (prevPts[i]) return prevPts[i];
    return [xAt(i), scale.y(sofar)];
  }

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
  const ahead = $derived(act !== null && active !== null && active > elapsed);
  const paceHere = $derived(
    ahead && projected !== null && active !== null ? paceAt(active, elapsed, n, sofar, projected) : null,
  );
  const prevHere = $derived(previous && active !== null ? previous[active] : null);
  const announce = $derived.by(() => {
    if (!act || active === null) return '';
    const parts = ahead
      ? [`${act.label}: not yet`]
      : [`${act.label}: ${formatMoney(act.earnings)}`, `running total ${formatMoney(totals[active])}`];
    if (paceHere !== null) parts.push(`at this pace ${formatMoney(paceHere)}`);
    if (prevHere !== null) parts.push(`${previousName} ${formatMoney(prevHere)}`);
    return parts.join(', ');
  });
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
      if (active === null && n) active = Math.max(0, elapsed);
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

          {#if prevPts.length > 1}
            <path d={prevD} class="prev" />
          {/if}
          {#if earnedPts.length > 1}
            <path d={areaD} fill="url(#{uid}-fill)" />
            <path d={lineD} class="line" stroke="url(#{uid}-line)" />
          {/if}
          {#if paceFrom && paceTo}
            <line class="pace" x1={paceFrom[0]} y1={paceFrom[1]} x2={paceTo[0]} y2={paceTo[1]} />
            <circle class="pace-end" cx={paceTo[0]} cy={paceTo[1]} r="3.5" />
          {/if}

          {#if act && active !== null}
            {@const p = anchor(active)}
            <line class="cross" x1={p[0]} x2={p[0]} y1="0" y2={plotH} />
            <circle class="dot" class:hollow={ahead} cx={p[0]} cy={p[1]} r="5" />
          {:else}
            {#if paceFrom}
              <circle class="dot end" cx={paceFrom[0]} cy={paceFrom[1]} r="4" />
              <text
                class="end-label"
                x={paceFrom[0] < plotW * 0.25 ? paceFrom[0] + 8 : paceFrom[0] - 8}
                y={paceFrom[1] - 10}
                text-anchor={n <= 1 ? 'middle' : paceFrom[0] < plotW * 0.25 ? 'start' : 'end'}
              >
                {formatMoney(sofar)}
              </text>
            {/if}
            {#if paceTo && paceLabel && projected !== null}
              <text class="end-label pace-label" x={paceTo[0] - 8} y={paceTo[1] - 10} text-anchor="end">
                {formatMoney(projected)}
              </text>
            {/if}
          {/if}

          {#each buckets as b, i (b.key)}
            {#if i % step === 0 || i === active}
              <text class="axis" class:axis-on={i === active} x={xAt(i)} y={plotH + 19} text-anchor="middle">{b.label}</text>
            {/if}
          {/each}
        </g>
      </svg>

      {#if act && active !== null}
        {@const p = anchor(active)}
        <ChartTooltip x={M.left + p[0]} y={M.top + p[1]} {width}>
          <div class="t-title">{act.label}</div>
          {#if ahead}
            <div class="t-row t-muted">Not worked yet</div>
            {#if paceHere !== null}<div class="t-row">At this pace <b>{formatMoney(paceHere)}</b></div>{/if}
          {:else}
            <div class="t-row">Earned <b>{formatMoney(act.earnings)}</b></div>
            <div class="t-row">Running total <b>{formatMoney(totals[active])}</b></div>
            <div class="t-row">Hours <b>{formatDuration(act.minutes)}</b></div>
          {/if}
          {#if prevHere !== null}
            <div class="t-row t-prev">{previousName} <b>{formatMoney(prevHere)}</b></div>
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
  .prev {
    fill: none;
    stroke: var(--text-subtle);
    stroke-width: 1.75;
    stroke-linecap: round;
    opacity: 0.55;
  }
  .pace {
    stroke: var(--chart-line-b);
    stroke-width: 2;
    stroke-dasharray: 5 5;
    stroke-linecap: round;
    opacity: 0.8;
  }
  .pace-end {
    fill: var(--glass-solid);
    stroke: var(--chart-line-b);
    stroke-width: 2;
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
  .dot.hollow {
    fill: var(--glass-solid);
    stroke: var(--chart-line-b);
    stroke-width: 2;
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
  .pace-label {
    fill: var(--text-muted);
    font-weight: 600;
  }
  .t-muted {
    color: var(--text-muted);
  }
  .t-prev {
    color: var(--text-muted);
  }
</style>
