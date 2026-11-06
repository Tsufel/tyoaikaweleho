<script lang="ts">
  import { onDestroy } from 'svelte';
  import { api, runFlow } from '../../lib/api';
  import type { Recovery, RecoveryResult } from '../../lib/api/types';
  import { fromIsoDateTime, hhmm, parseTimeInput } from '../../lib/time';
  import { pendingRecovery } from '../../lib/stores/recovery';
  import { timer } from '../../lib/stores/timer';
  import Button from '../../lib/ui/Button.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TimeInput from '../../lib/ui/TimeInput.svelte';
  import { elapsedHM, recoveryDate, recoveryEndNote, sinceText } from '../timer/timerLogic';

  /** §6.3: an unfinished shift from a crash or "Close anyway". Resume, Save
   *  and Discard go through Python, and a failure hands back a recovery, so App
   *  re-offers the modal. Escape resumes a fresh shift; one over the 8-hour
   *  limit is only put aside (the timer's banner offers it again), since
   *  resuming it would put days on the clock. */
  let { recovery, onresolved }: { recovery: Recovery; onresolved: (r: RecoveryResult) => void } = $props();

  type Action = 'resume' | 'save' | 'discard';
  const formId = `recover-${Math.random().toString(36).slice(2, 8)}`;
  // svelte-ignore state_referenced_locally
  let end = $state(recovery.suggested_end);
  let endError = $state('');
  let busy = $state<Action | null>(null);
  let now = $state(Date.now());
  const tick = setInterval(() => (now = Date.now()), 30_000);
  onDestroy(() => clearInterval(tick));

  const start = $derived(fromIsoDateTime(recovery.start_iso));
  const elapsed = $derived(elapsedHM(recovery.start_epoch_ms, now));
  const note = $derived(start ? recoveryEndNote(hhmm(start), end, $timer.pay_rate) : null);
  const stale = $derived(recovery.over_limit);

  async function run(action: Action, call: () => Promise<RecoveryResult>) {
    if (busy) return;
    busy = action;
    try {
      const r = await call();
      if (r.status === 'invalid') {
        endError = r.message;
        return;
      }
      if (r.status === 'cancelled') return;
      onresolved(r);
    } finally {
      busy = null;
    }
  }

  const resume = () => run('resume', () => api.recovery_resolve('resume'));
  const discard = () => run('discard', () => runFlow((c) => api.recovery_resolve('discard', null, c)));

  function save(e?: SubmitEvent) {
    e?.preventDefault();
    if (!parseTimeInput(end)) {
      endError = 'End time must be a valid time (e.g. 17:00).';
      return;
    }
    endError = '';
    void run('save', () => runFlow((c) => api.recovery_resolve('save', end, c)));
  }

  const putAside = () => pendingRecovery.set(null);
</script>

<Modal title="An unfinished shift was found" icon="warning" size="md" onclose={stale ? putAside : () => void resume()}>
  <p class="lead">
    {#if stale}
      The app was closed while a shift was running, started {sinceText(recovery.elapsed_minutes)}. Check the end
      time and save it, or discard it.
    {:else}
      The app was closed while a shift was running. Resume it, save it with an end time, or discard it.
    {/if}
  </p>

  <div class="ticket">
    <div class="stripe" aria-hidden="true"></div>
    <dl class="grid">
      <div><dt>Date</dt><dd>{recoveryDate(recovery.start_iso)}</dd></div>
      <div><dt>Job / Shift</dt><dd>{recovery.job_shift || '—'}</dd></div>
      <div><dt>Started</dt><dd class="num">{start ? hhmm(start) : '—'}</dd></div>
      <div><dt>Elapsed</dt><dd class="num">{elapsed}</dd></div>
    </dl>
  </div>

  {#if recovery.over_limit}
    <p class="note" role="note"><Icon name="warning" size={15} /> Over 8 hours — end time set to the 8-hour mark.</p>
  {/if}

  <form id={formId} class="end" onsubmit={save} novalidate>
    <label class="end-label" for="{formId}-end">End time (for Save):</label>
    <div class="end-row">
      <TimeInput
        id="{formId}-end"
        bind:value={end}
        invalid={!!endError}
        describedby="{formId}-hint"
        onchange={() => (endError = '')}
      />
      <span id="{formId}-hint" class="hint" class:error={!!endError} class:warn={!endError && note?.tone === 'warning'} aria-live="polite">
        {#if endError}
          {endError}
        {:else if note}
          {note.text}
        {/if}
      </span>
    </div>
  </form>

  {#snippet footer()}
    <div class="row">
      <Button variant="danger" icon="trash" loading={busy === 'discard'} disabled={!!busy && busy !== 'discard'} onclick={() => void discard()}>
        Discard
      </Button>
      <span class="grow"></span>
      <Button
        variant={stale ? 'primary' : 'secondary'}
        icon="check"
        type="submit"
        form={formId}
        data-autofocus={stale ? '' : undefined}
        loading={busy === 'save'}
        disabled={!!busy && busy !== 'save'}
      >
        Save
      </Button>
      <Button
        variant={stale ? 'secondary' : 'success'}
        glow={!stale}
        icon="play"
        data-autofocus={stale ? undefined : ''}
        loading={busy === 'resume'}
        disabled={!!busy && busy !== 'resume'}
        onclick={() => void resume()}
      >
        Resume
      </Button>
    </div>
  {/snippet}
</Modal>

<style>
  .lead {
    margin: 0 0 14px;
    color: var(--text-muted);
    line-height: 1.55;
  }
  .ticket {
    position: relative;
    display: flex;
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    background: var(--field-bg);
    overflow: hidden;
  }
  .stripe {
    flex: none;
    width: 5px;
    background: linear-gradient(180deg, var(--amber), var(--magenta), var(--violet));
  }
  .grid {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 18px;
    margin: 0;
    padding: 14px 16px;
  }
  dt {
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-subtle);
  }
  dd {
    margin: 2px 0 0;
    font-size: var(--fs-md);
    font-weight: 600;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .note {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 12px 0 0;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--amber) 14%, transparent);
    color: var(--warning-text);
    font-size: var(--fs-sm);
  }
  .end {
    margin-top: 16px;
  }
  .end-label {
    display: block;
    margin-bottom: 6px;
    font-size: var(--fs-sm);
    color: var(--text-muted);
  }
  .end-row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .end-row > :global(:first-child) {
    width: 150px;
  }
  .hint {
    font-size: var(--fs-sm);
    color: var(--text-subtle);
  }
  .hint.warn {
    color: var(--warning-text);
  }
  .hint.error {
    color: var(--danger-text);
  }
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
  }
  .grow {
    flex: 1;
  }
</style>
