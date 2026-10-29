<script lang="ts">
  import type { Snippet } from 'svelte';

  /** Glass tooltip anchored at (x, y) inside a positioned chart box; flips/clamps to stay inside. */
  let {
    x,
    y,
    width,
    children,
  }: { x: number; y: number; width: number; children: Snippet } = $props();

  let el = $state<HTMLDivElement>();
  let w = $state(160);
  let h = $state(60);

  $effect(() => {
    if (!el) return;
    const ro = new ResizeObserver(() => {
      w = el!.offsetWidth;
      h = el!.offsetHeight;
    });
    ro.observe(el);
    return () => ro.disconnect();
  });

  const left = $derived(Math.max(4, Math.min(width - w - 4, x - w / 2)));
  const below = $derived(y - h - 14 < 0);
  const top = $derived(below ? y + 14 : y - h - 14);
</script>

<div bind:this={el} class="tip glass-strong" style:left="{left}px" style:top="{top}px" aria-hidden="true">
  {@render children()}
</div>

<style>
  .tip {
    position: absolute;
    z-index: 3;
    min-width: 132px;
    padding: 10px 12px;
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    box-shadow: inset 0 1px 0 var(--glass-highlight), var(--shadow-lg);
    -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
    backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
    pointer-events: none;
    font-size: var(--fs-sm);
    color: var(--text);
    transition:
      left 120ms var(--ease-out),
      top 120ms var(--ease-out);
  }
  .tip :global(.t-title) {
    font-weight: 650;
    margin-bottom: 4px;
  }
  .tip :global(.t-row) {
    display: flex;
    justify-content: space-between;
    gap: 14px;
    color: var(--text-muted);
    line-height: 1.55;
  }
  .tip :global(.t-row b) {
    color: var(--text);
    font-family: var(--font-mono);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
</style>
