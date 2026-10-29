<script lang="ts" module>
  export const describedBy = (id: string) => `${id}-note`;
</script>

<script lang="ts">
  import type { Snippet } from 'svelte';

  /** Label + control + hint/error line. Give the control `id={forId}` and
   *  `aria-describedby={describedBy}` when hint/error is set. */
  let {
    label,
    forId,
    hint,
    error,
    class: cls = '',
    children,
  }: { label: string; forId: string; hint?: string | null; error?: string | null; class?: string; children: Snippet } =
    $props();

  export const describedBy = (id: string) => `${id}-note`;
</script>

<div class="field {cls}">
  <label for={forId}>{label}</label>
  {@render children()}
  {#if error}
    <p class="note error" id={describedBy(forId)} role="alert">{error}</p>
  {:else if hint}
    <p class="note" id={describedBy(forId)}>{hint}</p>
  {/if}
</div>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }
  label {
    font-size: var(--fs-sm);
    font-weight: 600;
    color: var(--text-muted);
  }
  .note {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    line-height: 1.4;
  }
  .error {
    color: var(--danger-text);
  }
</style>
