<script lang="ts">
  // All achievements, grouped by tier. Opened from the Stats tile, the unlock
  // card and the backfill toast (openAchievements).
  import { onMount } from 'svelte';
  import type { Achievement } from '../../lib/api/types';
  import { fly, stagger } from '../../lib/motion';
  import {
    achievements,
    achievementsError,
    achievementsLoading,
    checkAchievements,
    medalUrl,
    unlockedCount,
  } from '../../lib/stores/achievements';
  import Button from '../../lib/ui/Button.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import Spinner from '../../lib/ui/Spinner.svelte';
  import { TIERS, TIER_LABEL, progressText, shortDate } from './tiers';

  let { onclose }: { onclose: (r: void) => void } = $props();

  const items = $derived($achievements?.items ?? []);
  const total = $derived(items.length);
  const got = $derived(unlockedCount($achievements));
  const groups = $derived(
    TIERS.map((tier) => ({ tier, list: items.filter((a) => a.tier === tier) })).filter((g) => g.list.length),
  );

  const secret = (a: Achievement) => a.hidden && !a.met_on;
  const pct = (a: Achievement) => (a.progress.goal > 0 ? Math.min(100, (a.progress.cur / a.progress.goal) * 100) : 0);

  onMount(() => {
    if (!$achievements) void checkAchievements();
  });

  let errorBox = $state<HTMLElement>();
  let summary = $state<HTMLElement>();
  /** Retry had focus: once the list replaces it, focus the summary instead of <body>. */
  let refocus = false;

  function retry() {
    if ($achievementsLoading) return;
    refocus = !!errorBox?.contains(document.activeElement);
    void checkAchievements();
  }

  $effect(() => {
    if (!summary || !refocus) return;
    refocus = false;
    if (!document.activeElement || document.activeElement === document.body) summary.focus();
  });
</script>

<Modal title="Achievements" icon="success" size="lg" onclose={() => onclose()} closeButton class="achievements">
  {#if !$achievements && $achievementsError}
    <!-- Stays mounted while retrying (not disabled either) so the focused Retry keeps focus. -->
    <div class="center error" role="alert" bind:this={errorBox}>
      <p>{$achievementsError}</p>
      <Button onclick={retry} aria-busy={$achievementsLoading || undefined}>
        {$achievementsLoading ? 'Retrying…' : 'Retry'}
      </Button>
    </div>
  {:else if !$achievements}
    <div class="center"><Spinner size={24} label="Loading achievements" /></div>
  {:else}
    <div class="summary" tabindex="-1" bind:this={summary}>
      <span class="count"><strong>{got}</strong> / {total} unlocked</span>
      <span
        class="bar"
        role="progressbar"
        aria-label="Achievements unlocked"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={got}
      ><span style="width: {total ? (got / total) * 100 : 0}%"></span></span>
    </div>
    <div class="scroll">
      {#each groups as g, gi (g.tier)}
        <section class="group tier-{g.tier}" aria-labelledby="ach-{g.tier}">
          <h3 id="ach-{g.tier}">
            {TIER_LABEL[g.tier]}
            <span class="n">{g.list.filter((a) => a.met_on).length} / {g.list.length}</span>
          </h3>
          <ul>
            {#each g.list as a, i (a.id)}
              <li
                class="card"
                class:locked={!a.met_on}
                class:secret={secret(a)}
                in:fly|global={{ y: 10, delay: stagger(gi * 3 + i, 30, 16) }}
              >
                <img class="medal" src={medalUrl(a)} alt="" draggable="false" />
                <div class="info">
                  <span class="title">{secret(a) ? '???' : a.title}</span>
                  <span class="desc">{secret(a) ? 'Hidden achievement. Keep working to find it.' : a.desc}</span>
                  {#if a.met_on}
                    <span class="date">Unlocked {shortDate(a.met_on)}</span>
                  {:else if !secret(a) && a.progress.goal > 1}
                    <span class="prog">
                      <span class="track"><span style="width: {pct(a)}%"></span></span>
                      <span class="num">{progressText(a.progress.cur, a.progress.goal, a.progress.unit)}</span>
                    </span>
                  {/if}
                </div>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  {/if}
  {#snippet footer()}
    <Button variant="primary" onclick={() => onclose()} data-autofocus>Close</Button>
  {/snippet}
</Modal>

<style>
  .center {
    display: grid;
    place-items: center;
    gap: 12px;
    padding: 40px;
  }
  .error p {
    margin: 0;
    color: var(--text-muted);
  }
  .summary {
    outline: none;
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
  }
  .count {
    flex: none;
    font-size: var(--fs-sm);
    color: var(--text-muted);
  }
  .count strong {
    color: var(--text);
    font-size: var(--fs-lg);
  }
  .bar,
  .track {
    position: relative;
    flex: 1;
    height: 6px;
    border-radius: 999px;
    background: var(--divider);
    overflow: hidden;
  }
  .bar > span,
  .track > span {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--violet), var(--magenta));
    transition: width var(--dur-slow) var(--ease-out);
  }

  .scroll {
    max-height: min(60vh, 560px);
    overflow: auto;
    padding-right: 4px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .group {
    --tier: #d08a4a;
  }
  .tier-silver {
    --tier: #b8c4dc;
  }
  .tier-gold {
    --tier: var(--amber);
  }
  .tier-legendary {
    --tier: var(--magenta);
  }
  h3 {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin: 0 0 8px;
    font-size: var(--fs-sm);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--tier) 75%, var(--text));
  }
  h3 .n {
    font-weight: 500;
    letter-spacing: 0;
    color: var(--text-muted);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 8px;
  }
  .card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--tier) 9%, transparent);
    border: 1px solid color-mix(in srgb, var(--tier) 28%, transparent);
  }
  .card.locked {
    background: transparent;
    border-color: var(--divider);
  }
  .medal {
    flex: none;
    width: 56px;
    height: 56px;
    object-fit: contain;
    filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.3));
  }
  .locked .medal {
    filter: grayscale(1) brightness(0.8);
    opacity: 0.45;
  }
  .secret .medal {
    filter: none;
    opacity: 0.7;
  }
  .info {
    min-width: 0;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .title {
    font-weight: 700;
  }
  .locked .title {
    color: var(--text-muted);
  }
  .desc,
  .date,
  .num {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .date {
    color: color-mix(in srgb, var(--tier) 70%, var(--text));
    font-weight: 600;
  }
  .prog {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 3px;
  }
  .track {
    height: 4px;
  }
  .num {
    flex: none;
    font-variant-numeric: tabular-nums;
  }
</style>
