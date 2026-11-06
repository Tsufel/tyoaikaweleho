<script lang="ts">
  import { api } from '../../lib/api/bridge';
  import { fade, fly } from '../../lib/motion';
  import { unlockQueue } from '../../lib/stores/achievements';
  import { animationsActive, navigate, todayIso } from '../../lib/stores/app';
  import { fromIsoDate } from '../../lib/time';
  import { buildRecap, lastWeek, readShownWeek, writeShownWeek, type Recap, type RecapWeek } from './recap';

  /** Once per ISO week: a card summing up last week, on the first open of the
   *  new one. Gives way to modals, a running shift, the pet flyby and unlock
   *  cards (same spot), and only counts down while the window is watched.
   *  held/waiting: same meaning as for AchievementUnlock, both just wait here. */
  let { held = false, waiting = false }: { held?: boolean; waiting?: boolean } = $props();

  const ENTER_DELAY_MS = 1600;
  const SHOW_MS = 9000;
  const TICK_MS = 100;

  let recap = $state<Recap | null>(null);
  let shown = $state(false);
  /** Always-mounted live region: a freshly inserted one isn't reliably announced. */
  let announce = $state('');
  let card = $state<HTMLElement>();
  let key = '';
  let loading = false;
  let left = SHOW_MS;
  let returnFocus: HTMLElement | null = null;

  // Re-checked when the date rolls over, for a window left open across Monday.
  $effect(() => {
    const today = fromIsoDate($todayIso);
    if (today) void load(lastWeek(today));
  });

  async function load(week: RecapWeek) {
    if (loading || week.key === key || readShownWeek() === week.key) return;
    loading = true;
    try {
      const r = await api.get_stats(week.range.start, week.range.end, 'day');
      if (!r.ok || !r.data) return;
      const built = buildRecap(week, r.data, r.data.pay_rate);
      if (!built) {
        // Nothing worked last week: nothing to say, and no need to ask again.
        writeShownWeek(week.key);
        return;
      }
      key = week.key;
      left = SHOW_MS;
      recap = built;
    } catch {
      // Quiet: it tries again next launch.
    } finally {
      loading = false;
    }
  }

  const free = $derived(!!recap && !held && !waiting && $unlockQueue.length === 0);

  $effect(() => {
    if (!free) {
      shown = false;
      return;
    }
    let tick: ReturnType<typeof setInterval> | undefined;
    const enter = setTimeout(() => {
      if (!recap) return;
      shown = true;
      writeShownWeek(key);
      announce = `${recap.title}. ${recap.stats.map((s) => `${s.label} ${s.value}`).join(', ')}.`;
      tick = setInterval(() => {
        if (engaged() || !$animationsActive) return;
        left -= TICK_MS;
        if (left <= 0) close();
      }, TICK_MS);
    }, ENTER_DELAY_MS);
    return () => {
      clearTimeout(enter);
      clearInterval(tick);
    };
  });

  /** Hovered or focused, checked live: a card hidden mid-hover never gets its pointerleave. */
  const engaged = () => !!card && (card.matches(':hover') || card.contains(document.activeElement));

  function close() {
    if (card?.contains(document.activeElement) && returnFocus?.isConnected) returnFocus.focus();
    returnFocus = null;
    recap = null;
  }

  function openStats() {
    close();
    void navigate('stats');
  }

  function focusIn(e: FocusEvent) {
    if (e.relatedTarget instanceof HTMLElement && !card?.contains(e.relatedTarget)) returnFocus = e.relatedTarget;
  }
</script>

<div class="sr-only" role="status" aria-live="polite">{announce}</div>
{#if shown && recap}
  <div
    bind:this={card}
    class="recap glass glass-strong"
    role="group"
    aria-labelledby="recap-title"
    onfocusin={focusIn}
    in:fly|global={{ y: -24, duration: 420 }}
    out:fade|global={{ duration: 220 }}
  >
    <div class="body">
      <span class="kicker">Last week</span>
      <h2 id="recap-title" class="title">{recap.title}</h2>
      <span class="range">{recap.range}</span>
      <dl class="stats">
        {#each recap.stats as s (s.label)}
          <div><dt>{s.label}</dt><dd>{s.value}</dd></div>
        {/each}
      </dl>
      <p class="note">{recap.note}</p>
      <button type="button" class="link" onclick={openStats}>See stats</button>
    </div>
    <button type="button" class="close" aria-label="Dismiss" onclick={close}>×</button>
  </div>
{/if}

<style>
  .recap {
    position: fixed;
    top: 72px;
    left: 50%;
    translate: -50% 0;
    z-index: 150;
    width: min(400px, calc(100vw - 32px));
    display: flex;
    align-items: flex-start;
    border-radius: var(--radius-lg);
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      0 0 0 1px color-mix(in srgb, var(--violet) 40%, transparent),
      var(--shadow-lg);
  }
  .body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 12px 4px 12px 16px;
  }
  .kicker {
    font-size: var(--fs-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--violet) 70%, var(--text));
  }
  .title {
    margin: 0;
    font-size: var(--fs-lg);
    font-weight: 750;
    line-height: 1.2;
  }
  .range,
  .note {
    font-size: var(--fs-sm);
    color: var(--text-muted);
  }
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
    gap: 8px;
    margin: 10px 0 6px;
  }
  .stats div {
    display: flex;
    flex-direction: column-reverse;
  }
  dt {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  dd {
    margin: 0;
    font-size: var(--fs-md);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .note {
    margin: 0;
  }
  .link {
    align-self: flex-start;
    margin-top: 6px;
    padding: 0;
    border: 0;
    background: none;
    color: color-mix(in srgb, var(--violet) 75%, var(--text));
    font: inherit;
    font-size: var(--fs-sm);
    font-weight: 650;
    cursor: pointer;
  }
  .link:hover {
    text-decoration: underline;
  }
  .link:focus-visible,
  .close:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .close {
    flex: none;
    width: 32px;
    height: 32px;
    margin: 6px;
    border: 0;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--text-muted);
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
  }
  .close:hover {
    color: var(--text);
    background: var(--row-hover, rgba(255, 255, 255, 0.06));
  }
</style>
