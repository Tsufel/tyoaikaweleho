<script lang="ts">
  import { onDestroy } from 'svelte';
  import { api, runFlow } from '../../lib/api';
  import type { Recovery, RecoveryResult } from '../../lib/api/types';
  import { formatMoney, fromIsoDateTime, hhmm, parseTimeInput } from '../../lib/time';
  import { timer } from '../../lib/stores/timer';
  import Button from '../../lib/ui/Button.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TimeInput from '../../lib/ui/TimeInput.svelte';
  import { elapsedHM, recoveryDate } from '../timer/timerLogic';

  /** §6.3: an unfinished shift from a crash or "Close anyway". Only Resume
   *  dismisses it (Escape too); Save and Discard go through Python, and a
   *  failure hands back a recovery, so App re-offers the modal. */
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
  const endMinutes = $derived.by(() => {
    const t = parseTimeInput(end);
    if (!t || !start) return null;
    const [h, m] = t.split(':').map(Number);
    const s = start.getHours() * 60 + start.getMinutes();
    return (h * 60 + m - s + 1440) % 1440;
  });

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
    void run('save', () => api.recovery_resolve('save', end));
  }
</script>

<Modal title="An unfinished shift was found" icon="warning" size="md" onclose={() => void resume()}>
  <p class="lead">
    The app was closed while a shift was running. Resume it, save it with an end time, or discard it.
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
      <span id="{formId}-hint" class="hint" class:error={!!endError} aria-live="polite">
        {#if endError}
          {endError}
        {:else if endMinutes != null}
          {Math.floor(endMinutes / 60)}h {String(endMinutes % 60).padStart(2, '0')}m · {formatMoney((endMinutes / 60) * ($timer.pay_rate || 0))}
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
      <Button variant="secondary" icon="check" type="submit" form={formId} loading={busy === 'save'} disabled={!!busy && busy !== 'save'}>
        Save
      </Button>
      <Button
        variant="success"
        glow
        icon="play"
        data-autofocus
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
