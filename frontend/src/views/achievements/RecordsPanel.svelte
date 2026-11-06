<script lang="ts">
  // Hall of fame: personal records from get_records (records.py), at the top of
  // the Achievements sheet. Re-asked whenever achievements are (same triggers);
  // a failed load just leaves the panel out, records never block anything.
  import { api } from '../../lib/api/bridge';
  import type { RecordsData } from '../../lib/api/types';
  import { achievements } from '../../lib/stores/achievements';
  import { recordTiles } from './records';

  let data = $state<RecordsData | null>(null);
  let seq = 0;

  async function load() {
    const mine = ++seq;
    try {
      const r = await api.get_records();
      if (mine === seq && r?.ok) data = r;
    } catch {
      // keep what we had
    }
  }

  $effect(() => {
    void $achievements; // re-read with every achievements check
    void load();
  });

  const tiles = $derived(data ? recordTiles(data) : []);
</script>

{#if data}
  <section class="records" aria-labelledby="ach-records">
    <h3 id="ach-records">Hall of fame</h3>
    {#if data.total_shifts === 0}
      <p class="empty">Your records show up here after your first shift.</p>
    {:else}
      <dl>
        {#each tiles as t (t.label)}
          <div class="tile">
            <dt>{t.label}</dt>
            <dd class="v">{t.value}</dd>
            {#if t.sub}<dd class="sub">{t.sub}</dd>{/if}
          </div>
        {/each}
      </dl>
    {/if}
  </section>
{/if}

<style>
  .records {
    padding: 12px;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--violet) 30%, transparent);
    background: color-mix(in srgb, var(--violet) 7%, transparent);
  }
  h3 {
    margin: 0 0 8px;
    font-size: var(--fs-sm);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--violet) 70%, var(--text));
  }
  dl {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px 14px;
  }
  .tile {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  dt,
  .sub,
  .empty {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  dd {
    margin: 0;
  }
  .v {
    font-weight: 700;
    font-size: var(--fs-lg);
    font-variant-numeric: tabular-nums;
  }
  .sub {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .empty {
    margin: 0;
  }
</style>
