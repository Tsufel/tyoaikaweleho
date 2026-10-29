<script lang="ts">
  import type { ConfirmRendererProps } from '../../lib/stores/confirm';
  import Button from '../../lib/ui/Button.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import { arrowNav } from './arrowNav';
  import OptionCard from './OptionCard.svelte';

  /** §6.2 start_ahead: the picked start time is still ahead of now. */
  let { request, onchoose }: ConfirmRendererProps<'start_ahead'> = $props();

  const msgId = `ahead-msg-${Math.random().toString(36).slice(2, 8)}`;
  let done = false;

  function pick(id: string) {
    if (done) return;
    done = true;
    onchoose(id as 'now' | 'earlier' | 'cancel');
  }

  const DESC: Record<string, string> = {
    now: 'The shift starts at the current time.',
    earlier: 'Back-dates the start; the elapsed time counts from then.',
  };
  const cards = $derived(request.options.filter((o) => o.id !== 'cancel'));
</script>

<Modal
  title={request.title}
  icon={request.icon}
  size="md"
  role="alertdialog"
  describedby={msgId}
  initialFocus={`[data-choice="${request.default}"]`}
  onclose={() => pick(request.cancel)}
>
  <p id={msgId} class="msg">{request.message}</p>
  <div class="cards" use:arrowNav>
    {#each cards as o (o.id)}
      <OptionCard
        id={o.id}
        title={o.label}
        description={DESC[o.id] ?? ''}
        icon={o.id === 'now' ? 'play' : 'clock'}
        tone={o.id === request.default ? 'success' : 'primary'}
        onpick={pick}
      />
    {/each}
  </div>
  {#snippet footer()}
    {#if request.options.some((o) => o.id === 'cancel')}
      <Button variant="ghost" data-choice="cancel" onclick={() => pick('cancel')}>Cancel</Button>
    {/if}
  {/snippet}
</Modal>

<style>
  .msg {
    white-space: pre-line;
    color: var(--text-muted);
    line-height: 1.55;
    font-size: var(--fs-md);
  }
  .cards {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 16px;
  }
</style>
