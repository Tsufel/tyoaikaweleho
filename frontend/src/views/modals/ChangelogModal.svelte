<script lang="ts">
  // "What's new" — shown once after an update, before crash recovery (§6.7).
  import type { ChangelogBlock } from '../../lib/api/types';
  import { fly, stagger } from '../../lib/motion';
  import { bootstrap } from '../../lib/stores/app';
  import Button from '../../lib/ui/Button.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { blocks, onclose }: { blocks: ChangelogBlock[]; onclose: () => void } = $props();

  const verKey = (v: string) => v.split('.').map((x) => Number.parseInt(x, 10) || 0);
  function cmp(a: string, b: string): number {
    const x = verKey(a);
    const y = verKey(b);
    for (let i = 0; i < Math.max(x.length, y.length); i++) {
      const d = (y[i] ?? 0) - (x[i] ?? 0);
      if (d) return d;
    }
    return 0;
  }
  const sorted = $derived([...blocks].sort((a, b) => cmp(a.version, b.version)));
  const version = $derived($bootstrap?.version ?? sorted[0]?.version ?? '');

</script>

<Modal title="What's new in v{version}" icon="success" size="md" {onclose} closeButton class="changelog">
  <div class="log">
    {#each sorted as b, bi (b.version)}
      <section class="block" in:fly={{ y: 10, delay: stagger(bi, 70) }}>
        <h3>
          <span class="chip mono" class:latest={bi === 0}>v{b.version}</span>
          {#if bi === 0}<span class="tag">Latest</span>{/if}
        </h3>
        <ul>
          {#each b.items as it, i (i)}
            <li in:fly={{ x: -8, delay: stagger(bi * 4 + i, 35, 14) + 80 }}>
              <span class="dot" aria-hidden="true"><Icon name="sparkles" size={13} /></span>
              <span>{it}</span>
            </li>
          {/each}
        </ul>
      </section>
    {/each}
  </div>
  {#snippet footer()}
    <Button variant="success" glow icon="check" onclick={onclose} data-autofocus>Got it</Button>
  {/snippet}
</Modal>

<style>
  .log {
    display: flex;
    flex-direction: column;
    gap: 18px;
    max-height: min(52vh, 460px);
    overflow: auto;
    padding-right: 4px;
  }
  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .chip {
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
    font-size: var(--fs-sm);
    font-weight: 700;
    color: var(--text-muted);
  }
  .chip.latest {
    color: var(--on-accent);
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    box-shadow: 0 4px 18px var(--accent-glow);
  }
  .tag {
    font-size: var(--fs-xs);
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent-text);
  }
  ul {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  li {
    display: flex;
    gap: 10px;
    line-height: 1.45;
  }
  .dot {
    flex: none;
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    margin-top: 1px;
    border-radius: 8px;
    color: var(--accent-text);
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }
</style>
