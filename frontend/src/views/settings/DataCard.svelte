<script lang="ts">
  import { onMount } from 'svelte';
  import { fly, stagger } from '../../lib/motion';
  import { bootstrap } from '../../lib/stores/app';
  import Button from '../../lib/ui/Button.svelte';
  import GlassCard from '../../lib/ui/GlassCard.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import {
    backupDetail,
    backups,
    backupsError,
    backupStatus,
    backupNow,
    dataBusy,
    formatSavedAt,
    KIND_LABELS,
    loadBackups,
    openDataFolder,
    restoreBackup,
  } from './dataFlow';

  interface Props {
    /** Position in the Settings grid's entrance stagger. */
    index?: number;
  }
  let { index = 7 }: Props = $props();

  let restoring = $state<string | null>(null);
  let showList = $state(false);

  const dataDir = $derived($bootstrap?.data_dir ?? '');
  const status = $derived(backupStatus($backups));
  const busy = $derived($dataBusy !== null && $dataBusy !== 'list');

  async function restore(name: string) {
    if (busy) return;
    restoring = name;
    try {
      await restoreBackup(name);
    } finally {
      restoring = null;
    }
  }

  onMount(() => void loadBackups());
</script>

<GlassCard tag="section" class="card" aria-labelledby="s-data" padding="20px" radius="lg">
  <div class="card-in" in:fly={{ y: 12, delay: stagger(index, 50) }}>
    <h3 id="s-data"><Icon name="file" size={16} /> Your data</h3>
    <p class="muted small">
      Shifts and settings are saved on this PC{#if dataDir}&nbsp;in <span class="mono path">{dataDir}</span>{/if}.
    </p>
    <p class="status small" aria-live="polite">
      {#if $backupsError}<span class="bad">{$backupsError}</span>{:else}{status}{/if}
    </p>
    <div class="actions">
      <Button variant="secondary" icon="download" loading={$dataBusy === 'backup'} disabled={busy} onclick={() => void backupNow()}>
        Back up now
      </Button>
      <Button variant="ghost" icon="external" onclick={() => void openDataFolder()}>Open data folder</Button>
    </div>
    {#if $backups.length}
      <button type="button" class="link small" aria-expanded={showList} aria-controls="backup-list" onclick={() => (showList = !showList)}>
        {showList ? 'Hide backups' : 'Restore a backup…'}
      </button>
      {#if showList}
        <ul id="backup-list" class="list" aria-label="Backups, newest first" in:fly={{ y: 6 }}>
          {#each $backups as b (b.name)}
            <li class:bad-row={!b.ok}>
              <div class="b-main">
                <div class="b-head">
                  <span class="row-title">{formatSavedAt(b.saved_at)}</span>
                  <span class="kind">{KIND_LABELS[b.kind]}</span>
                </div>
                <div class="muted small">{backupDetail(b)}</div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon="undo"
                label={`Restore the backup from ${formatSavedAt(b.saved_at)}`}
                loading={restoring === b.name}
                disabled={!b.ok || busy}
                onclick={() => void restore(b.name)}
              >
                Restore
              </Button>
            </li>
          {/each}
        </ul>
        <p class="muted small">Restoring asks first and copies your current data to the backups folder before anything is replaced.</p>
      {/if}
    {/if}
  </div>
</GlassCard>

<style>
  .card-in {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--fs-md);
    font-weight: 700;
    color: var(--text);
  }
  h3 :global(svg) {
    color: var(--accent-text);
  }
  .small {
    font-size: var(--fs-sm);
  }
  .path {
    word-break: break-all;
  }
  .bad {
    color: var(--danger-text);
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .link {
    align-self: flex-start;
    border: 0;
    padding: 0;
    background: none;
    font: inherit;
    font-weight: 650;
    color: var(--accent-text);
    text-decoration: underline;
    cursor: pointer;
  }
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    max-height: 280px;
    overflow-y: auto;
    border-top: 1px solid var(--divider);
  }
  .list li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 2px;
    border-bottom: 1px solid var(--divider);
  }
  .b-main {
    min-width: 0;
  }
  .b-head {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 8px;
  }
  .row-title {
    font-weight: 650;
  }
  .kind {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .bad-row .b-main {
    opacity: 0.7;
  }
</style>
