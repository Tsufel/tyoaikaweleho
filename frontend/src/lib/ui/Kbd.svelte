<script lang="ts">
  /** 'Ctrl+N' → Ctrl + N keycaps. */
  let { keys = '' }: { keys?: string } = $props();
  const parts = $derived(keys.length > 1 ? keys.split(/\+(?!$)/) : [keys]);
</script>

<!-- aria-label is not allowed on a plain span: read the combo as text -->
<span class="kbd">
  <span class="sr-only">{keys}</span>
  {#each parts as k, i (i)}
    <kbd aria-hidden="true">{k}</kbd>
  {/each}
</span>

<style>
  .kbd {
    display: inline-flex;
    gap: 3px;
    vertical-align: middle;
  }
  kbd {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    line-height: 1;
    padding: 3px 6px 4px;
    min-width: 20px;
    text-align: center;
    border-radius: 6px;
    background: var(--neutral-fill);
    border: 1px solid var(--glass-border);
    border-bottom-width: 2px;
    color: var(--text-muted);
  }
</style>
