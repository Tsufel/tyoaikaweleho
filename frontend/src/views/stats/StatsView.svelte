<script lang="ts" module>
  import type { Granularity } from '../../lib/api/types';
  import type { DateRange, Preset } from './ranges';

  // Remembered while the app runs (the view is remounted on every visit).
  const memory: { preset: Preset; offset: number; granularity: Granularity | null; custom: DateRange | null } = {
    preset: 'month',
    offset: 0,
    granularity: null,
    custom: null,
  };
</script>

<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { api, onEvent } from '../../lib/api';
  import type { StatsBucket, StatsData } from '../../lib/api/types';
  import { navigate, section, settings, shifts } from '../../lib/stores/app';
  import { setViewMonth, showEntry } from '../../lib/stores/entries';
  import { achievements, medalUrl, openAchievements, unlockedCount } from '../../lib/stores/achievements';
  import { timer } from '../../lib/stores/timer';
  import { fade, fly, stagger } from '../../lib/motion';
  import { formatDuration, formatMoney, fromIsoDate } from '../../lib/time';
  import { Button, CalendarPopover, GlassCard, Icon, Segmented, Spinner, tooltip } from '../../lib/ui';
  import AreaChart from '../../charts/AreaChart.svelte';
  import BarChart from '../../charts/BarChart.svelte';
  import DonutChart from '../../charts/DonutChart.svelte';
  import { bucketTargets, shiftSlices } from '../../charts/chartUtils';
  import KpiTile from './KpiTile.svelte';
  import {
    GRANULARITIES,
    PRESETS,
    defaultGranularity,
    fitGranularity,
    formatRange,
    granularityAllowed,
    periodTitle,
    presetRange,
    shiftRange,
    validateRange,
  } from './ranges';

  let preset = $state<Preset>(memory.preset);
  let offset = $state(memory.offset);
  let custom = $state<DateRange>(memory.custom ?? presetRange('month', new Date()));

  const range = $derived<DateRange>(preset === 'custom' ? custom : presetRange(preset, new Date(), offset));
  const rangeError = $derived(preset === 'custom' ? validateRange(custom) : null);

  const initialRange = (): DateRange =>
    memory.preset === 'custom' ? custom : presetRange(memory.preset, new Date(), memory.offset);
  let granularity = $state<Granularity>(memory.granularity ?? defaultGranularity(memory.preset, initialRange()));

  const granOptions = $derived(GRANULARITIES.filter((g) => granularityAllowed(g.value, range)));

  $effect(() => {
    const fit = fitGranularity(granularity, preset, range);
    if (fit !== granularity) granularity = fit;
  });

  $effect(() => {
    memory.preset = preset;
    memory.offset = offset;
    memory.granularity = granularity;
    memory.custom = custom;
  });

  function pickPreset(p: Preset) {
    if (p === 'custom') custom = { ...range };
    preset = p;
    offset = 0;
    granularity = defaultGranularity(p, p === 'custom' ? custom : presetRange(p, new Date()));
  }

  function stepPeriod(dir: -1 | 1) {
    if (preset === 'custom') custom = shiftRange(custom, dir);
    else offset += dir;
  }

  // ── data ───────────────────────────────────────────────────────
  let data = $state<StatsData | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let seq = 0;

  async function load() {
    if (rangeError) return;
    const mySeq = ++seq;
    loading = true;
    const r = await api.get_stats(range.start, range.end, granularity);
    if (mySeq !== seq) return;
    loading = false;
    if (r.ok && r.data) {
      data = r.data;
      error = null;
    } else {
      error = r.status === 'error' ? r.error.message : (r.message ?? 'Could not load stats.');
    }
  }

  $effect(() => {
    void range.start;
    void range.end;
    void granularity;
    void $settings.pay_rate;
    void load();
  });

  const offs: (() => void)[] = [];
  onMount(() => {
    offs.push(onEvent('data:changed', () => void load()));
    offs.push(onEvent('timer:changed', () => void load()));
    let wasRunning = get(timer).running;
    offs.push(
      timer.subscribe((t) => {
        if (wasRunning && !t.running) void load();
        wasRunning = t.running;
      }),
    );
  });
  onDestroy(() => offs.forEach((f) => f()));

  // ── derived view model ─────────────────────────────────────────
  const targetHours = $derived($settings.ui_prefs.target_hours);
  const targets = $derived(data ? bucketTargets(data.buckets, data.granularity, data.start, data.end, targetHours) : []);
  const slices = $derived(data ? shiftSlices(data.by_shift, $shifts) : []);
  const achTotal = $derived($achievements?.items.length || 17);
  // all-time, newest first: the tile ignores the picked range
  const latestAch = $derived(
    ($achievements?.items ?? [])
      .filter((a) => a.met_on)
      .sort((a, b) => (a.met_on! < b.met_on! ? 1 : a.met_on! > b.met_on! ? -1 : 0))
      .slice(0, 3),
  );
  const empty = $derived(!!data && data.totals.shifts === 0);
  const unit = $derived(data?.granularity ?? granularity);
  const unitWord = $derived(unit === 'day' ? 'day' : unit === 'week' ? 'week' : 'month');
  const metTarget = $derived(
    data ? data.buckets.filter((b, i) => targets[i] > 0 && b.minutes / 60 >= targets[i]).length : 0,
  );
  // Days: out of the days worked (weekends have no target of their own); weeks/months: those with weekdays.
  const targetBuckets = $derived(
    !data ? 0 : unit === 'day' ? data.buckets.filter((b) => b.minutes > 0).length : targets.filter((t) => t > 0).length,
  );

  let showTable = $state(false);

  // ── pickers ────────────────────────────────────────────────────
  let startBtn = $state<HTMLButtonElement>();
  let endBtn = $state<HTMLButtonElement>();
  let picking = $state<'start' | 'end' | null>(null);

  const dateText = (iso: string) => {
    const d = fromIsoDate(iso);
    return d ? d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : iso;
  };

  // ── drill-down ─────────────────────────────────────────────────
  async function openBucket(b: StatsBucket) {
    const d = fromIsoDate(b.start);
    if (!d || !(await navigate('main'))) return;
    section.set('shifts');
    await setViewMonth(d.getFullYear(), d.getMonth() + 1);
  }

  async function openLongest() {
    const l = data?.longest;
    if (!l || !(await navigate('main'))) return;
    section.set('shifts');
    await showEntry(l.entry);
  }

  const shiftsWord = (n: number) => `${n} ${n === 1 ? 'shift' : 'shifts'}`;
</script>

<div class="stats">
  <header class="bar glass" in:fly={{ y: -8 }}>
    <div class="title">
      <h2>{periodTitle(preset, offset, range)}</h2>
      <p class="range num">{formatRange(range)}</p>
    </div>

    <div class="nav">
      <button
        type="button"
        class="chev lg-gel"
        aria-label="Previous period"
        use:tooltip={'Previous period'}
        disabled={!!rangeError}
        onclick={() => stepPeriod(-1)}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>
      </button>
      <Button
        variant="ghost"
        size="sm"
        disabled={preset !== 'custom' && offset === 0}
        tooltip="Back to the current period"
        onclick={() => (preset === 'custom' ? pickPreset('month') : (offset = 0))}
      >
        Now
      </Button>
      <button
        type="button"
        class="chev lg-gel"
        aria-label="Next period"
        use:tooltip={'Next period'}
        disabled={!!rangeError}
        onclick={() => stepPeriod(1)}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
      </button>
    </div>

    <div class="controls">
      <Segmented value={preset} options={PRESETS} label="Range" size="sm" onchange={pickPreset} />
      <Segmented bind:value={granularity} options={granOptions} label="Group by" size="sm" />
    </div>

    {#if preset === 'custom'}
      <div class="custom" transition:fly={{ y: -6 }}>
        <span class="lbl" id="stats-from">From</span>
        <button
          bind:this={startBtn}
          type="button"
          class="date-btn num"
          aria-labelledby="stats-from stats-from-v"
          aria-haspopup="dialog"
          aria-expanded={picking === 'start'}
          onclick={() => (picking = picking === 'start' ? null : 'start')}
        >
          <Icon name="calendar" size={15} /><span id="stats-from-v">{dateText(custom.start)}</span>
        </button>
        <span class="lbl" id="stats-to">to</span>
        <button
          bind:this={endBtn}
          type="button"
          class="date-btn num"
          aria-labelledby="stats-to stats-to-v"
          aria-haspopup="dialog"
          aria-expanded={picking === 'end'}
          onclick={() => (picking = picking === 'end' ? null : 'end')}
        >
          <Icon name="calendar" size={15} /><span id="stats-to-v">{dateText(custom.end)}</span>
        </button>
        {#if rangeError}<span class="err" role="alert">{rangeError}</span>{/if}
      </div>
    {/if}
  </header>

  {#if error && !data}
    <GlassCard class="state" tag="section">
      <Icon name="error" size={28} />
      <p>{error}</p>
      <Button variant="primary" icon="refresh" onclick={() => void load()}>Try again</Button>
    </GlassCard>
  {:else if !data}
    <div class="kpis" aria-hidden="true">
      {#each Array(6) as _, i (i)}<div class="tile-skel glass"></div>{/each}
    </div>
    <div class="center"><Spinner size={28} label="Loading stats" /></div>
  {:else}
    <p class="note" in:fade>
      <Icon name="info" size={14} />
      <span>
        Earnings use your current pay rate ({formatMoney(data.pay_rate)}/h), also for older shifts.
        {#if data.open_entries > 0}
          {shiftsWord(data.open_entries)} without an end time {data.open_entries === 1 ? 'is' : 'are'} left out.
        {/if}
      </span>
      {#if loading}<Spinner size={14} label="Updating" />{/if}
      {#if error}<span class="err" role="alert">{error}</span>{/if}
    </p>

    <section class="kpis" aria-label="Summary" class:busy={loading}>
      <div in:fly={{ y: 14, delay: stagger(0, 50) }}>
        <KpiTile icon="clock" label="Total hours" value={data.totals.minutes} format={formatDuration} tone="violet">
          {#snippet sub()}{shiftsWord(data!.totals.shifts)}{/snippet}
        </KpiTile>
      </div>
      <div in:fly={{ y: 14, delay: stagger(1, 50) }}>
        <KpiTile icon="euro" label="Earnings" value={data.totals.earnings} format={formatMoney} tone="cyan" delay={60}>
          {#snippet sub()}at {formatMoney(data!.pay_rate)}/h{/snippet}
        </KpiTile>
      </div>
      <div in:fly={{ y: 14, delay: stagger(2, 50) }}>
        <KpiTile
          icon="chart"
          label="Avg per worked day"
          value={data.avg_per_worked_day.minutes}
          format={formatDuration}
          tone="magenta"
          delay={120}
        >
          {#snippet sub()}{formatMoney(data!.avg_per_worked_day.earnings)} per day{/snippet}
        </KpiTile>
      </div>
      <div in:fly={{ y: 14, delay: stagger(3, 50) }}>
        <KpiTile
          icon="flame"
          label="Longest shift"
          value={data.longest?.minutes ?? 0}
          format={formatDuration}
          tone="amber"
          delay={180}
        >
          {#snippet sub()}
            {#if data!.longest}
              <button type="button" class="link" onclick={openLongest}>
                {data!.longest.entry.display_date}{data!.longest.entry.job_shift ? ` · ${data!.longest.entry.job_shift}` : ''}
              </button>
            {:else}—{/if}
          {/snippet}
        </KpiTile>
      </div>
      <div in:fly={{ y: 14, delay: stagger(4, 50) }}>
        <KpiTile
          icon="calendar"
          label="Days worked"
          value={data.totals.worked_days}
          format={(n) => String(Math.round(n))}
          tone="teal"
          delay={240}
        >
          {#snippet sub()}
            {#if targetBuckets > 0 && !empty}
              {metTarget} of {targetBuckets} {unit === 'day' ? 'worked days' : `${unitWord}s`} at target
            {:else}
              {data!.totals.worked_days === 1 ? 'day' : 'days'} with hours
            {/if}
          {/snippet}
        </KpiTile>
      </div>
      <div in:fly={{ y: 14, delay: stagger(5, 50) }}>
        <KpiTile
          icon="trophy"
          label="Achievements"
          value={unlockedCount($achievements)}
          format={(n) => `${Math.round(n)} / ${achTotal}`}
          tone="amber"
          delay={300}
        >
          {#snippet sub()}
            <span class="ach">
              {#each latestAch as a (a.id)}<img src={medalUrl(a)} alt={a.title} title={a.title} />{/each}
              <button type="button" class="link" onclick={() => void openAchievements()}>
                {latestAch.length ? 'View all' : 'See what to unlock'}
              </button>
            </span>
          {/snippet}
        </KpiTile>
      </div>
    </section>

    {#if empty}
      <div in:fly={{ y: 16, delay: stagger(5, 50) }}>
        <GlassCard class="state empty" tag="section" aria-labelledby="stats-empty">
          <span class="empty-orb" aria-hidden="true"><Icon name="chart" size={30} /></span>
          <h3 id="stats-empty">No shifts in this period</h3>
          <p>Hours you clock in this range will show up here. Try another range or press START on the timer.</p>
          <Button variant="secondary" icon="timer" onclick={() => void navigate('main')}>Go to timer</Button>
        </GlassCard>
      </div>
    {:else}
      <div class="charts" class:busy={loading}>
        <div class="span-2" in:fly={{ y: 16, delay: stagger(5, 50) }}>
          <GlassCard tag="section" padding="18px 20px 14px" aria-labelledby="stats-hours">
            <div class="card-head">
              <h3 id="stats-hours">Hours per {unitWord}</h3>
              <span class="legend-inline">
                <span class="key bar-key" aria-hidden="true"></span>Hours
                {#if targetBuckets > 0}<span class="key target-key" aria-hidden="true"></span>Target ({targetHours}h/day){/if}
              </span>
              <Button
                variant="ghost"
                size="sm"
                icon={showTable ? 'chart' : 'list'}
                aria-pressed={showTable}
                onclick={() => (showTable = !showTable)}
              >
                {showTable ? 'Chart' : 'Table'}
              </Button>
            </div>
            {#if showTable}
              <div class="table-wrap" in:fade>
                <table>
                  <thead>
                    <tr><th scope="col">{unitWord[0].toUpperCase() + unitWord.slice(1)}</th><th scope="col">Hours</th><th scope="col">Earnings</th><th scope="col">Shifts</th></tr>
                  </thead>
                  <tbody>
                    {#each data.buckets as b (b.key)}
                      <tr class:zero={b.minutes === 0}>
                        <th scope="row">{b.label}</th>
                        <td class="num">{formatDuration(b.minutes)}</td>
                        <td class="num">{formatMoney(b.earnings)}</td>
                        <td class="num">{b.shifts}</td>
                      </tr>
                    {/each}
                  </tbody>
                  <tfoot>
                    <tr>
                      <th scope="row">Total</th>
                      <td class="num">{formatDuration(data.totals.minutes)}</td>
                      <td class="num">{formatMoney(data.totals.earnings)}</td>
                      <td class="num">{data.totals.shifts}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            {:else}
              <BarChart
                buckets={data.buckets}
                {targets}
                label="Hours per {unitWord}, {formatRange(range)}"
                onopen={openBucket}
              />
            {/if}
          </GlassCard>
        </div>

        <div in:fly={{ y: 16, delay: stagger(6, 50) }}>
          <GlassCard tag="section" padding="18px 20px 14px" aria-labelledby="stats-earn">
            <div class="card-head">
              <h3 id="stats-earn">Earnings, running total</h3>
              <span class="big num">{formatMoney(data.totals.earnings)}</span>
            </div>
            <AreaChart buckets={data.buckets} label="Running total of earnings, {formatRange(range)}" />
          </GlassCard>
        </div>

        <div in:fly={{ y: 16, delay: stagger(7, 50) }}>
          <GlassCard tag="section" padding="18px 20px" aria-labelledby="stats-jobs">
            <div class="card-head">
              <h3 id="stats-jobs">By job / shift</h3>
            </div>
            <DonutChart {slices} label="Hours by job or shift" />
          </GlassCard>
        </div>
      </div>
    {/if}
  {/if}
</div>

{#if picking === 'start'}
  <CalendarPopover
    anchor={startBtn}
    value={custom.start}
    onpick={(iso) => (custom = { ...custom, start: iso })}
    onclose={() => (picking = null)}
  />
{:else if picking === 'end'}
  <CalendarPopover
    anchor={endBtn}
    value={custom.end}
    onpick={(iso) => (custom = { ...custom, end: iso })}
    onclose={() => (picking = null)}
  />
{/if}

<style>
  .stats {
    /* categorical slots — validated (dataviz validator) on #18173a / #fbfaff */
    --series-1: #8b6cff;
    --series-2: #0aa3bb;
    --series-3: #e0559a;
    --series-4: #c4880c;
    --series-5: #139c86;
    --series-other: #6d6b93;
    --chart-bar-a: #5b3ef0;
    --chart-bar-b: #a78bfa;
    --chart-bar-hot: #22d3ee;
    --chart-target: #fbbf24;
    --chart-target-text: var(--warning-text);
    --chart-area: #22d3ee;
    --chart-line-a: #8b6cff;
    --chart-line-b: #22d3ee;
    --chart-glow: rgba(124, 92, 255, 0.55);
    --chart-glow-2: rgba(34, 211, 238, 0.45);

    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-bottom: 24px;
    min-width: 0;
  }
  :global(:root[data-theme='light']) .stats {
    --series-1: #6847f5;
    --series-2: #0e8aa5;
    --series-3: #d1437f;
    --series-4: #b97806;
    --series-5: #0f8a73;
    --series-other: #a3a0c2;
    --chart-bar-a: #6847f5;
    --chart-bar-b: #a78bfa;
    --chart-bar-hot: #0e8aa5;
    --chart-target: #c2690a;
    --chart-area: #0e8aa5;
    --chart-line-a: #6847f5;
    --chart-line-b: #0e8aa5;
    --chart-glow: rgba(104, 71, 245, 0.35);
    --chart-glow-2: rgba(14, 138, 165, 0.3);
  }

  .bar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      'title nav'
      'controls controls'
      'custom custom';
    align-items: center;
    gap: 12px 16px;
    padding: 16px 20px;
    border-radius: var(--radius-xl);
  }
  @media (min-width: 1100px) {
    .bar {
      grid-template-columns: minmax(0, 1fr) auto auto;
      grid-template-areas:
        'title controls nav'
        'custom custom custom';
    }
  }
  .title {
    grid-area: title;
    min-width: 0;
  }
  h2 {
    margin: 0;
    font-size: var(--fs-xl);
    font-weight: 750;
    letter-spacing: -0.02em;
  }
  .range {
    margin: 2px 0 0;
    color: var(--text-muted);
    font-size: var(--fs-sm);
  }
  .nav {
    grid-area: nav;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .chev {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border: 1px solid var(--glass-border);
    border-radius: 50%;
    background: var(--neutral-fill);
    color: var(--text);
    cursor: pointer;
    transition:
      background var(--dur-fast),
      transform var(--dur-fast),
      box-shadow var(--dur-med);
  }
  .chev svg {
    fill: none;
    stroke: currentColor;
    stroke-width: 2.4;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .chev:hover:not(:disabled) {
    background: var(--neutral-fill-hover);
    box-shadow: 0 0 18px -4px var(--accent-glow);
  }
  .chev:active:not(:disabled) {
    transform: scale(0.94);
  }
  .chev:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .chev:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .controls {
    grid-area: controls;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }
  .custom {
    grid-area: custom;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .lbl {
    color: var(--text-muted);
    font-size: var(--fs-sm);
  }
  .date-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 32px;
    padding: 0 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--field-border);
    background: var(--field-bg);
    color: var(--text);
    font-size: var(--fs-sm);
    cursor: pointer;
    transition:
      background var(--dur-fast),
      transform var(--dur-fast);
  }
  .date-btn:hover {
    background: var(--field-bg-focus);
  }
  .date-btn:active {
    transform: scale(0.97);
  }
  .date-btn:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .err {
    color: var(--danger-text);
    font-size: var(--fs-sm);
    font-weight: 600;
  }

  .note {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin: -4px 4px 0;
    color: var(--text-muted);
    font-size: var(--fs-xs);
  }

  /* 6 tiles: 3×2, one row when wide, 2×3 when narrow (never a lone orphan) */
  .kpis {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    transition: opacity var(--dur-med);
  }
  @media (min-width: 1280px) {
    .kpis {
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }
  }
  @media (max-width: 600px) {
    .kpis {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  .kpis > div {
    min-width: 0;
    display: flex;
  }
  .kpis > div > :global(*) {
    flex: 1;
  }
  .tile-skel {
    height: 112px;
    border-radius: var(--radius-lg);
    opacity: 0.6;
  }
  .busy {
    opacity: 0.72;
  }
  .center {
    display: grid;
    place-items: center;
    padding: 48px 0;
  }

  .charts {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    transition: opacity var(--dur-med);
  }
  .span-2 {
    grid-column: 1 / -1;
  }
  @media (max-width: 860px) {
    .charts {
      grid-template-columns: minmax(0, 1fr);
    }
  }
  .card-head {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }
  .card-head h3 {
    margin: 0;
    font-size: var(--fs-md);
    font-weight: 650;
    margin-right: auto;
  }
  .big {
    font-size: var(--fs-lg);
    font-weight: 700;
  }
  .legend-inline {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--text-muted);
    font-size: var(--fs-xs);
  }
  .key {
    display: inline-block;
    margin-left: 8px;
  }
  .bar-key {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    background: linear-gradient(0deg, var(--chart-bar-a), var(--chart-bar-b));
  }
  .target-key {
    width: 16px;
    border-top: 2px dashed var(--chart-target);
  }

  .table-wrap {
    max-height: 260px;
    overflow: auto;
    border-radius: var(--radius-md);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-sm);
  }
  th,
  td {
    padding: 6px 10px;
    text-align: right;
    border-bottom: 1px solid var(--divider);
  }
  th:first-child {
    text-align: left;
  }
  thead th {
    position: sticky;
    top: 0;
    background: var(--glass-solid);
    color: var(--text-muted);
    font-weight: 600;
  }
  tbody th {
    font-weight: 500;
  }
  tr.zero td {
    color: var(--text-subtle);
  }
  tfoot th,
  tfoot td {
    font-weight: 700;
    border-bottom: 0;
  }

  .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent-text);
    font: inherit;
    cursor: pointer;
    text-decoration: underline;
    text-decoration-color: color-mix(in srgb, var(--accent-text) 40%, transparent);
    text-underline-offset: 2px;
    text-align: left;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ach {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }
  .ach img {
    width: 22px;
    height: 22px;
    object-fit: contain;
  }
  .ach .link {
    margin-left: 4px;
  }
  .link:focus-visible {
    outline: 2px solid var(--focus-ring);
    border-radius: 4px;
  }

  .stats :global(.state) {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    text-align: center;
    padding: 40px 24px;
  }
  .stats :global(.state h3) {
    margin: 4px 0 0;
    font-size: var(--fs-lg);
  }
  .stats :global(.state p) {
    margin: 0;
    max-width: 44ch;
    color: var(--text-muted);
  }
  .empty-orb {
    display: grid;
    place-items: center;
    width: 72px;
    height: 72px;
    border-radius: 50%;
    color: var(--on-accent);
    background: radial-gradient(circle at 30% 30%, var(--chart-bar-b), var(--accent-strong) 60%, var(--accent-strong-2));
    box-shadow: 0 10px 40px -6px var(--accent-glow);
  }

  /* Liquid glass: clear chips (icon only) with gel press */
  :global(:root[data-glass='liquid']) .chev {
    background: linear-gradient(180deg, var(--lg-sheen), transparent 60%), var(--lg-clear);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }
  :global(:root[data-glass='liquid']) .chev:hover:not(:disabled) {
    background: linear-gradient(180deg, var(--lg-sheen), transparent 60%), var(--neutral-fill-hover);
    box-shadow: inset 0 1px 0 var(--glass-highlight), 0 0 18px -4px var(--accent-glow);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .chev.lg-gel {
    transition:
      background var(--dur-fast),
      transform var(--dur-fast),
      box-shadow var(--dur-med),
      scale 460ms var(--lg-spring);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .chev.lg-gel:active:not(:disabled) {
    transform: none;
    scale: 1.06 0.94;
    transition-duration: var(--dur-fast), var(--dur-fast), var(--dur-med), 90ms;
  }
</style>
