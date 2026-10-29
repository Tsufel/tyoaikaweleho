<script lang="ts">
  import type { ConfirmRendererProps } from '../../lib/stores/confirm';
  import { timer } from '../../lib/stores/timer';
  import Modal from '../../lib/ui/Modal.svelte';
  import { arrowNav } from '../timer/arrowNav';
  import OptionCard from '../timer/OptionCard.svelte';
  import ShiftSummary from '../timer/ShiftSummary.svelte';

  /** §6.8 close_running: Stop & close / Close anyway (shift kept for recovery) /
   *  Stay. Escape = request.cancel (stay open). */
  let { request, onchoose }: ConfirmRendererProps<'close_running'> = $props();

  type Choice = 'stop_close' | 'close' | 'cancel';
  const msgId = `close-msg-${Math.random().toString(36).slice(2, 8)}`;
  let done = false;

  function pick(id: string) {
    if (done) return;
    done = true;
    onchoose(id as Choice);
  }

  const CARDS: Record<Choice, { title: string; description: string; icon: 'stop' | 'x' | 'play'; tone: 'success' | 'neutral' | 'primary' }> = {
    stop_close: { title: 'Stop, save & close', description: 'Saves the shift ending now, then closes.', icon: 'stop', tone: 'success' },
    close: {
      title: 'Close anyway',
      description: 'The shift keeps its start time and is offered for recovery next time.',
      icon: 'x',
      tone: 'neutral',
    },
    cancel: { title: 'Stay open', description: 'Keep working; nothing changes.', icon: 'play', tone: 'primary' },
  };

  const startIso = $derived(request.details?.start_iso ?? $timer.start_iso ?? '');
  const options = $derived(request.options.filter((o): o is typeof o & { id: Choice } => o.id in CARDS));
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
  {#if startIso}
    <ShiftSummary {startIso} elapsedMinutes={request.details?.elapsed_minutes ?? 0} job={$timer.job_shift} />
  {/if}
  <p class="msg" aria-hidden="true">A shift is still running. Save it before closing?</p>
  <p id={msgId} class="sr-only">{request.message}</p>
  <div class="cards" use:arrowNav>
    {#each options as o (o.id)}
      {@const c = CARDS[o.id]}
      <OptionCard
        id={o.id}
        title={o.id === 'stop_close' ? c.title : o.label || c.title}
        description={c.description}
        icon={c.icon}
        tone={c.tone}
        hint={o.id === request.default ? 'Enter' : o.id === request.cancel ? 'Esc' : ''}
        onpick={pick}
      />
    {/each}
  </div>
</Modal>

<style>
  .msg {
    color: var(--text-muted);
    line-height: 1.55;
    font-size: var(--fs-md);
    margin: 0 0 12px;
  }
  .cards {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
</style>
