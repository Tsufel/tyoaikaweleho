<script lang="ts">
  // OCR preview: editable rows, uncheck to skip, then import (v1.3 OcrPreviewDialog).
  import { api } from '../../lib/api';
  import type { OcrCandidate, OcrSaveResult } from '../../lib/api/types';
  import { fly, stagger } from '../../lib/motion';
  import { reportError } from '../../lib/stores/confirm';
  import { tooltip } from '../../lib/ui/actions';
  import Button from '../../lib/ui/Button.svelte';
  import Combobox from '../../lib/ui/Combobox.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TextInput from '../../lib/ui/TextInput.svelte';
  import TimeInput from '../../lib/ui/TimeInput.svelte';
  import { allState, clipRaw, draftRows, issueText, rowIssue, rowsToSave, selectedCount } from './ocrLogic';

  let {
    candidates,
    errors = [],
    shifts = [],
    defaultShift = '',
    onclose,
  }: {
    candidates: OcrCandidate[];
    errors?: string[];
    shifts?: string[];
    defaultShift?: string;
    onclose: (r: OcrSaveResult | null) => void;
  } = $props();

  // svelte-ignore state_referenced_locally
  let rows = $state(draftRows(candidates, defaultShift));
  let saving = $state(false);
  let showErrors = $state(false);

  const count = $derived(selectedCount(rows));
  const all = $derived(allState(rows));
  const uncertain = $derived(rows.filter((r) => r.uncertain).length);
  const title = $derived(`OCR Preview — ${candidates.length} entr${candidates.length === 1 ? 'y' : 'ies'} detected`);

  let headBox = $state<HTMLInputElement>();
  $effect(() => {
    if (headBox) headBox.indeterminate = all === 'some';
  });

  function toggleAll() {
    const on = all !== 'all';
    for (const r of rows) r.checked = on;
  }

  async function importRows() {
    if (!count || saving) return;
    saving = true;
    try {
      const r = await api.ocr_save(rowsToSave(rows));
      if (!r.ok) {
        await reportError(r, 'Import failed');
        return;
      }
      onclose(r);
    } finally {
      saving = false;
    }
  }

  const close = () => {
    if (!saving) onclose(null);
  };
</script>

<Modal {title} size="xl" onclose={close} closeButton class="ocr-sheet">
  <div class="intro-line">
    <p class="muted">Review detected entries. Uncheck rows to skip; edit fields as needed.</p>
    {#if uncertain}
      <span class="pill amber"><Icon name="warning" size={13} /> {uncertain} uncertain</span>
    {/if}
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="c-check">
            <input
              bind:this={headBox}
              type="checkbox"
              checked={all === 'all'}
              onchange={toggleAll}
              aria-label={all === 'all' ? 'Deselect all rows' : 'Select all rows'}
            />
          </th>
          <th>Date</th>
          <th>Job shift</th>
          <th>Time in</th>
          <th>Time out</th>
          <th>OCR text</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row, i (row.key)}
          {@const issue = row.checked ? rowIssue(row) : null}
          {@const note = issueText(issue)}
          <tr
            class:uncertain={row.uncertain}
            class:off={!row.checked}
            in:fly={{ y: 6, delay: stagger(i, 22, 16) }}
          >
            <td class="c-check">
              <input type="checkbox" bind:checked={row.checked} aria-label="Import row {i + 1}" />
            </td>
            <td class="c-date">
              <TextInput
                bind:value={row.date}
                size="sm"
                mono
                invalid={issue === 'date'}
                placeholder="YYYY-MM-DD"
                aria-label="Date, row {i + 1}"
                disabled={!row.checked}
              />
            </td>
            <td class="c-shift">
              <Combobox
                bind:value={row.job_shift}
                options={shifts}
                size="sm"
                label="Job shift, row {i + 1}"
                disabled={!row.checked}
              />
            </td>
            <td>
              <TimeInput
                bind:value={row.time_in}
                size="sm"
                label="Time in, row {i + 1}"
                invalid={issue === 'time_in'}
                disabled={!row.checked}
              />
            </td>
            <td>
              <TimeInput
                bind:value={row.time_out}
                size="sm"
                label="Time out, row {i + 1}"
                invalid={issue === 'time_out'}
                disabled={!row.checked}
              />
            </td>
            <td class="c-raw">
              <span class="raw mono" use:tooltip={row.raw_line.length > 55 ? row.raw_line : null}>
                {clipRaw(row.raw_line)}
              </span>
              {#if row.uncertain}
                <span class="badge" use:tooltip={'OCR was unsure about this row — check the values'}>
                  <Icon name="warning" size={12} /> Check
                </span>
              {/if}
              {#if note}<span class="issue" role="note">{note}</span>{/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if errors.length}
    <div class="errors">
      <button type="button" class="err-toggle" aria-expanded={showErrors} onclick={() => (showErrors = !showErrors)}>
        <Icon name={showErrors ? 'chevron-down' : 'chevron-right'} size={14} />
        {errors.length} image{errors.length === 1 ? '' : 's'} could not be read
      </button>
      {#if showErrors}
        <ul>
          {#each errors as e, i (i)}<li class="mono">{e}</li>{/each}
        </ul>
      {/if}
    </div>
  {/if}

  {#snippet footer()}
    <span class="count muted" aria-live="polite">{count} of {rows.length} selected</span>
    <Button variant="ghost" onclick={close} disabled={saving}>Cancel</Button>
    <Button variant="primary" glow icon="download" loading={saving} disabled={!count} onclick={importRows} data-autofocus>
      Import selected ({count})
    </Button>
  {/snippet}
</Modal>

<style>
  .intro-line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    flex: none;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    font-size: var(--fs-xs);
    font-weight: 650;
  }
  .amber {
    color: var(--warning-text);
    background: color-mix(in srgb, var(--amber) 16%, transparent);
  }
  .table-wrap {
    max-height: min(56vh, 520px);
    overflow: auto;
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: 9px 8px;
    text-align: left;
    font-size: var(--fs-xs);
    font-weight: 650;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    background: var(--glass-bg-strong, var(--glass-bg));
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--divider);
  }
  td {
    padding: 6px 8px;
    vertical-align: middle;
    border-bottom: 1px solid var(--divider);
  }
  tbody tr {
    transition: background var(--dur-fast) var(--ease-out), opacity var(--dur-fast) var(--ease-out);
  }
  tbody tr:hover {
    background: var(--row-hover);
  }
  tr.uncertain {
    background: color-mix(in srgb, var(--amber) 10%, transparent);
    box-shadow: inset 3px 0 0 var(--amber);
  }
  tr.uncertain:hover {
    background: color-mix(in srgb, var(--amber) 15%, transparent);
  }
  tr.off {
    opacity: 0.5;
  }
  .c-check {
    width: 36px;
    text-align: center;
  }
  input[type='checkbox'] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
    cursor: pointer;
  }
  .c-date {
    width: 140px;
  }
  .c-shift {
    min-width: 160px;
  }
  .c-raw {
    min-width: 200px;
    max-width: 320px;
  }
  .raw {
    display: block;
    font-size: var(--fs-xs);
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    padding: 1px 7px;
    border-radius: var(--radius-pill);
    font-size: var(--fs-xs);
    font-weight: 650;
    color: var(--warning-text);
    background: color-mix(in srgb, var(--amber) 18%, transparent);
  }
  .issue {
    display: block;
    margin-top: 3px;
    font-size: var(--fs-xs);
    color: var(--danger-text);
  }
  .errors {
    margin-top: 12px;
  }
  .err-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 6px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--danger-text);
    font: inherit;
    font-size: var(--fs-sm);
    cursor: pointer;
  }
  .err-toggle:hover {
    background: var(--neutral-fill-hover);
  }
  .errors ul {
    margin: 6px 0 0 26px;
    font-size: var(--fs-xs);
    color: var(--text-muted);
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .count {
    margin-right: auto;
    font-size: var(--fs-sm);
  }
</style>
