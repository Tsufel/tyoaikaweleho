<script lang="ts">
  import { api, runFlow } from '../../lib/api';
  import type { EntryDraft, EntryRow } from '../../lib/api/types';
  import { fade } from '../../lib/motion';
  import { reportError } from '../../lib/stores/confirm';
  import { settings, shifts } from '../../lib/stores/settings';
  import { addHours, durationNote, parseDateInput, parseTimeInput } from '../../lib/time';
  import Button from '../../lib/ui/Button.svelte';
  import CalendarPopover from '../../lib/ui/CalendarPopover.svelte';
  import Combobox from '../../lib/ui/Combobox.svelte';
  import Field from '../../lib/ui/Field.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TextInput from '../../lib/ui/TextInput.svelte';
  import TimeInput from '../../lib/ui/TimeInput.svelte';

  /** Add / edit an entry (v1.3 EditEntryDialog). Enter saves, Esc cancels. */
  let {
    entry,
    defaultDate,
    onclose,
  }: { entry: EntryRow | null; defaultDate: string; onclose: (saved: EntryRow | null) => void } = $props();

  type FieldName = 'date' | 'job_shift' | 'time_in' | 'time_out';

  function initial(): EntryDraft {
    if (entry) {
      return { id: entry.id, date: entry.date, job_shift: entry.job_shift, time_in: entry.time_in, time_out: entry.time_out };
    }
    const start = $settings.default_start_time;
    return {
      date: defaultDate,
      job_shift: $settings.default_job_shift || $shifts[0] || '',
      time_in: start,
      time_out: parseTimeInput(start) ? addHours(parseTimeInput(start)!, 8) : '',
    };
  }

  const init = initial();
  let date = $state(init.date);
  let job = $state(init.job_shift);
  let timeIn = $state(init.time_in);
  let timeOut = $state(init.time_out);
  let errors = $state<Partial<Record<FieldName, string>>>({});
  let saveError = $state<string | null>(null);
  let saving = $state(false);

  /** Esc / × / Cancel; ignored while a save is in flight. */
  function dismiss() {
    if (!saving) onclose(null);
  }
  let calOpen = $state(false);
  let calBtn = $state<HTMLButtonElement>();
  const els: Partial<Record<FieldName, HTMLInputElement>> = $state({});

  const note = $derived(durationNote(timeIn, timeOut));
  const dateIso = $derived(parseDateInput(date));

  function clear(f: FieldName) {
    if (errors[f]) errors = { ...errors, [f]: undefined };
  }

  async function save(e?: Event) {
    e?.preventDefault();
    if (saving) return;
    saving = true;
    saveError = null;
    const draft: EntryDraft = { date, job_shift: job.trim(), time_in: timeIn, time_out: timeOut };
    if (entry) draft.id = entry.id;
    try {
      const r = await runFlow((c) => api.save_entry(draft, c));
      if (r.ok) {
        if (r.status === 'saved' && r.entry) onclose(r.entry);
        return;
      }
      if (r.status === 'invalid') {
        const f = (['date', 'job_shift', 'time_in', 'time_out'] as const).find((x) => x === r.field);
        if (f) {
          errors = { [f]: r.message };
          els[f]?.focus();
          els[f]?.select();
        } else await reportError(r, 'Invalid input');
      } else if (r.status === 'error') {
        if (r.error.code === 'internal') await reportError(r);
        else saveError = `${r.error.message}\n\nNothing you typed was lost — press Save again.`;
      }
    } finally {
      saving = false;
    }
  }
</script>

<Modal title={entry ? 'Edit shift' : 'Add shift'} icon={entry ? 'info' : 'success'} onclose={dismiss} closeButton initialFocus="#em-date">
  <form id="entry-form" class="form" onsubmit={save} novalidate>
    <Field label="Date" forId="em-date" error={errors.date} hint="e.g. 2026-09-23 or 23.9.">
      <TextInput
        id="em-date"
        bind:value={date}
        bind:el={els.date}
        mono
        invalid={!!errors.date}
        aria-describedby="em-date-note"
        oninput={() => clear('date')}
      >
        {#snippet trailing()}
          <button
            bind:this={calBtn}
            type="button"
            class="cal"
            aria-label="Choose date"
            aria-haspopup="dialog"
            aria-expanded={calOpen}
            onclick={() => (calOpen = !calOpen)}
          >
            <Icon name="calendar" size={16} />
          </button>
        {/snippet}
      </TextInput>
    </Field>

    <Field label="Job / Shift" forId="em-job" error={errors.job_shift}>
      <Combobox
        id="em-job"
        bind:value={job}
        bind:el={els.job_shift}
        options={$shifts}
        allowCustom
        label="Job / Shift"
        invalid={!!errors.job_shift}
        describedby={errors.job_shift ? 'em-job-note' : undefined}
        onchange={() => clear('job_shift')}
      />
    </Field>

    <div class="times">
      <Field label="Time In (HH:MM)" forId="em-in" error={errors.time_in}>
        <TimeInput
          id="em-in"
          bind:value={timeIn}
          bind:el={els.time_in}
          label="Time In"
          invalid={!!errors.time_in}
          describedby={errors.time_in ? 'em-in-note' : 'em-duration'}
          onchange={() => clear('time_in')}
        />
      </Field>
      <Field label="Time Out (HH:MM)" forId="em-out" error={errors.time_out}>
        <TimeInput
          id="em-out"
          bind:value={timeOut}
          bind:el={els.time_out}
          label="Time Out"
          invalid={!!errors.time_out}
          describedby={errors.time_out ? 'em-out-note' : 'em-duration'}
          onchange={() => clear('time_out')}
        />
      </Field>
    </div>

    <p id="em-duration" class="duration num" class:warning={note.tone === 'warning'} aria-live="polite">
      {#if note.tone === 'warning'}<Icon name="warning" size={15} />{:else}<Icon name="clock" size={15} />{/if}
      <span>{note.text}</span>
    </p>

    {#if saveError}
      <div class="save-error" role="alert" transition:fade={{ duration: 160 }}>
        <Icon name="error" size={16} />
        <p>{saveError}</p>
      </div>
    {/if}
  </form>

  {#snippet footer()}
    <Button variant="secondary" disabled={saving} onclick={dismiss}>Cancel</Button>
    <Button variant="primary" glow icon="check" type="submit" form="entry-form" loading={saving}>Save</Button>
  {/snippet}
</Modal>

{#if calOpen}
  <CalendarPopover anchor={calBtn} value={dateIso} onpick={(iso) => ((date = iso), clear('date'))} onclose={() => (calOpen = false)} />
{/if}

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .times {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  @media (max-width: 420px) {
    .times {
      grid-template-columns: 1fr;
    }
  }
  .cal {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition:
      background var(--dur-fast) var(--ease-out),
      color var(--dur-fast) var(--ease-out),
      transform var(--dur-fast) var(--ease-out);
  }
  .cal:hover {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
  .cal:active {
    transform: scale(0.94);
  }
  .cal:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--focus-ring);
  }
  .duration {
    display: flex;
    align-items: center;
    gap: 7px;
    margin: 0;
    min-height: 1.4em;
    color: var(--text-muted);
    font-size: var(--fs-sm);
    font-variant-numeric: tabular-nums;
    white-space: pre-wrap;
  }
  .duration.warning {
    color: var(--warning-text);
    font-weight: 600;
  }
  .save-error {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 10px 12px;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--danger) 45%, transparent);
    background: color-mix(in srgb, var(--danger) 12%, transparent);
    color: var(--danger-text);
    font-size: var(--fs-sm);
  }
  .save-error p {
    margin: 0;
    white-space: pre-wrap;
  }
</style>
