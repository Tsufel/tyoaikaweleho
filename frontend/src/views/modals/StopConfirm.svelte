<script lang="ts" module>
  export type StopKind = 'stop_shift' | 'long_shift' | 'over_24h' | 'discard_shift';
</script>

<script lang="ts">
  import type { ConfirmChoices, ConfirmDetails, ConfirmRequest } from '../../lib/api/types';
  import { timer } from '../../lib/stores/timer';
  import { formatDuration, fromIsoDateTime, hhmm } from '../../lib/time';
  import Button, { type ButtonVariant } from '../../lib/ui/Button.svelte';
  import type { IconName } from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import { arrowNav } from '../timer/arrowNav';
  import OptionCard from '../timer/OptionCard.svelte';
  import ShiftSummary from '../timer/ShiftSummary.svelte';

  /** Renderer for the §6.1 stop chain: stop_shift (F5), long_shift (>14 h),
   *  over_24h (save capped / discard / keep) and discard_shift. Escape answers
   *  request.cancel, which always keeps the shift. */
  let {
    request,
    onchoose,
  }: { request: ConfirmRequest<StopKind>; onchoose: (choice: ConfirmChoices[StopKind]) => void } = $props();

  const msgId = `stop-msg-${Math.random().toString(36).slice(2, 8)}`;
  let done = false;

  function pick(id: string) {
    if (done) return;
    done = true;
    onchoose(id as ConfirmChoices[StopKind]);
  }

  const d: ConfirmDetails = $derived(request.details ?? {});
  const job = $derived($timer.running && $timer.start_iso === d.start_iso ? $timer.job_shift : '');
  const startHHMM = $derived.by(() => {
    const s = d.start_iso ? fromIsoDateTime(d.start_iso) : null;
    return s ? hhmm(s) : '';
  });
  const isDiscard = $derived(request.kind === 'discard_shift');
  const tone: 'danger' | 'warning' | 'accent' = $derived(isDiscard ? 'danger' : request.icon === 'warning' ? 'warning' : 'accent');

  const LABELS: Record<string, string> = { stop: 'Stop & save', keep: 'Keep running', discard: 'Discard shift', cancel: 'Go back' };

  function variantOf(o: { id: string; variant?: string }): ButtonVariant {
    if (o.variant === 'danger') return 'danger';
    if (o.id === 'stop') return 'primary';
    return o.id === request.default || o.variant === 'primary' ? 'primary' : 'secondary';
  }

  function cardFor(o: { id: string; label: string; variant?: string }): {
    title: string;
    description: string;
    icon: IconName;
    tone: 'primary' | 'danger' | 'neutral';
  } {
    if (o.id === 'save')
      return {
        title: o.label,
        description: `Saves ${startHHMM || 'the shift'}–${d.capped_end ?? '8 h'} (8 hours). Fix the end time in the table afterwards.`,
        icon: 'check',
        tone: 'primary',
      };
    if (o.id === 'discard')
      return { title: 'Discard shift', description: 'Throws this shift away. You will be asked once more.', icon: 'trash', tone: 'danger' };
    return { title: o.label, description: 'Leave the timer running; nothing is saved yet.', icon: 'play', tone: 'neutral' };
  }
</script>

<Modal
  title={request.title}
  icon={isDiscard ? 'warning' : request.icon}
  size={request.kind === 'over_24h' ? 'md' : 'sm'}
  role="alertdialog"
  describedby={msgId}
  initialFocus={`[data-choice="${request.default}"]`}
  onclose={() => pick(request.cancel)}
>
  {#if d.start_iso}
    <ShiftSummary startIso={d.start_iso} elapsedMinutes={d.elapsed_minutes ?? 0} {job} {tone} />
  {/if}
  <p id={msgId} class="msg">{request.message}</p>

  {#if request.kind === 'over_24h'}
    <div class="cards" use:arrowNav>
      {#each request.options as o (o.id)}
        {@const c = cardFor(o)}
        <OptionCard id={o.id} title={c.title} description={c.description} icon={c.icon} tone={c.tone} onpick={pick} />
      {/each}
    </div>
  {/if}

  {#snippet footer()}
    {#if request.kind !== 'over_24h'}
      <div class="row" use:arrowNav>
        {#each request.options as o (o.id)}
          <Button
            variant={variantOf(o)}
            glow={o.id === request.default && o.id !== 'cancel'}
            icon={o.id === 'stop' ? 'stop' : o.id === 'discard' ? 'trash' : o.id === 'keep' ? 'play' : undefined}
            data-choice={o.id}
            onclick={() => pick(o.id)}
          >
            {LABELS[o.id] ?? o.label}
          </Button>
        {/each}
      </div>
    {:else if d.elapsed_minutes}
      <p class="foot-note">Running for {formatDuration(d.elapsed_minutes)}: one entry can hold at most 24 hours.</p>
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
  .row {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 10px;
  }
  .foot-note {
    margin: 0;
    font-size: var(--fs-xs);
    color: var(--text-subtle);
  }
</style>
