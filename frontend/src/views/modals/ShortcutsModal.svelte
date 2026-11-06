<script lang="ts">
  import { SHORTCUT_GROUPS } from '../../lib/shortcutList';
  import Button from '../../lib/ui/Button.svelte';
  import Kbd from '../../lib/ui/Kbd.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  /** The keyboard cheat sheet (? / F1). Esc or Close shuts it. */
  let { onclose }: { onclose: () => void } = $props();
</script>

<Modal title="Keyboard shortcuts" icon="info" size="lg" {onclose} closeButton initialFocus="[data-autofocus]">
  <div class="groups">
    {#each SHORTCUT_GROUPS as g (g.title)}
      <section aria-labelledby="keys-{g.title}">
        <h3 id="keys-{g.title}">{g.title}</h3>
        <table class="keys">
          <tbody>
            {#each g.rows as r (r.what)}
              <tr>
                <td class="k">
                  {#each r.keys as k, i (k)}
                    {#if i}<span class="or"> or </span>{/if}
                    {#if k.startsWith('Click')}<span class="hint">{k}</span>{:else}<Kbd keys={k} />{/if}
                  {/each}
                </td>
                <td>{r.what}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/each}
  </div>
  {#snippet footer()}
    <Button variant="primary" data-autofocus onclick={onclose}>Close</Button>
  {/snippet}
</Modal>

<style>
  .groups {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 18px 28px;
  }
  h3 {
    margin-bottom: 6px;
    font-size: var(--fs-sm);
    font-weight: 650;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .keys {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-sm);
  }
  td {
    padding: 5px 0;
    vertical-align: middle;
  }
  .k {
    width: 46%;
    padding-right: 12px;
    white-space: nowrap;
  }
  .or,
  .hint {
    color: var(--text-muted);
    font-size: var(--fs-xs);
  }
</style>
