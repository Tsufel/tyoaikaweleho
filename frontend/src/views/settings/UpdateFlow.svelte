<script lang="ts">
  // Always mounted: startup update prompt (update:*), DLC update notice,
  // and the blocking download overlays for app updates and DLC installs.
  import { onMount } from 'svelte';
  import { onEvent } from '../../lib/api';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import Progress from '../../lib/ui/Progress.svelte';
  import { overlay, updateEvents } from './updateFlow';

  onMount(() => {
    const offs = [
      onEvent('update:available', updateEvents.available),
      onEvent('update:installing', updateEvents.installing),
      onEvent('update:failed', updateEvents.failed),
      onEvent('dlc:update', updateEvents.dlcUpdate),
    ];
    return () => offs.forEach((f) => f());
  });

  const noteId = 'busy-overlay-note';
</script>

{#if $overlay}
  {#key $overlay.kind}
    <!-- no onclose: a download can't be cancelled (v1.3) -->
    <Modal size="sm" title={$overlay.title} describedby={noteId} class="busy-overlay">
      <div class="busy" aria-live="polite">
        <div class="glyph fx-anim" class:dlc={$overlay.kind === 'dlc'} aria-hidden="true">
          <span class="ring"></span>
          <Icon name={$overlay.kind === 'dlc' ? 'puzzle' : 'download'} size={26} />
        </div>
        <p class="msg">{$overlay.message}</p>
        <Progress label={$overlay.message} />
        {#if $overlay.note}<p id={noteId} class="note">{$overlay.note}</p>{/if}
      </div>
    </Modal>
  {/key}
{/if}

<style>
  .busy {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 6px 0 4px;
    text-align: center;
  }
  .glyph {
    position: relative;
    display: grid;
    place-items: center;
    width: 72px;
    height: 72px;
    color: var(--accent-text);
  }
  .glyph.dlc {
    color: var(--info-text);
  }
  .ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: conic-gradient(from 0deg, transparent 0 55%, var(--violet) 75%, var(--cyan) 100%);
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 4px), #000 calc(100% - 3px));
    mask: radial-gradient(farthest-side, transparent calc(100% - 4px), #000 calc(100% - 3px));
    animation: spin 1.1s linear infinite;
    filter: drop-shadow(0 0 10px var(--accent-glow));
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  .msg {
    font-weight: 650;
  }
  .busy :global(.progress) {
    width: 100%;
  }
  .note {
    font-size: var(--fs-sm);
    color: var(--text-muted);
    line-height: 1.45;
  }
</style>
