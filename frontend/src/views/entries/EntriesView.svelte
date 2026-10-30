<script lang="ts">
  import { onMount, tick } from 'svelte';
  import wizard from '../../assets/wizard.webp';
  import { api, runFlow } from '../../lib/api';
  import type { EntryRow, WorkEntry } from '../../lib/api/types';
  import { fade, flip, fly, stagger } from '../../lib/motion';
  import { registerCommand, SHORTCUT_LABELS } from '../../lib/shortcuts';
  import { alert, openSheet, reportError } from '../../lib/stores/confirm';
  import { registerEditGuard } from '../../lib/stores/editGuard';
  import {
    goToCurrentMonth,
    month,
    monthError,
    monthLoading,
    refreshMonth,
    selectedId,
    setViewMonth,
    shiftMonth,
    showEntry,
    viewMonth,
  } from '../../lib/stores/entries';
  import { dlc } from '../../lib/stores/settings';
  import { toast } from '../../lib/stores/toasts';
  import { defaultEntryDate, formatHM, formatMoney, monthLabel } from '../../lib/time';
  import Button from '../../lib/ui/Button.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Menu, { type MenuItem } from '../../lib/ui/Menu.svelte';
  import Spinner from '../../lib/ui/Spinner.svelte';
  import { openOcrImport } from '../ocr/ocrImport';
  import {
    buildRows,
    decideClose,
    EMPTY_HINT,
    emptyText,
    importSummary,
    moveSelection,
    parseEditor,
    weekTotalText,
    type EditField,
  } from './entriesLogic';
  import EntryModal from './EntryModal.svelte';
  import MonthPicker from './MonthPicker.svelte';

  interface Editor {
    id: string;
    field: EditField;
    /** Stored value when the editor first opened (the "unchanged" check). */
    original: string;
    invalid: boolean;
  }

  const rows = $derived(buildRows($month));
  const ids = $derived($month?.entries.map((e) => e.id) ?? []);
  const selected = $derived($month?.entries.find((e) => e.id === $selectedId) ?? null);
  const label = $derived($month?.label ?? monthLabel($viewMonth.year, $viewMonth.month));

  let editor = $state<Editor | null>(null);
  let editorEl = $state<HTMLInputElement>();
  /** Kept outside `editor` so the input binding never reads a closed editor. */
  let editText = $state('');
  let pending: Promise<boolean> | null = null;
  /** Typed value shown in the cell while its save is in flight. */
  let saving = $state<{ id: string; field: EditField; value: string } | null>(null);

  let tbody = $state<HTMLElement>();
  let importBtn = $state<HTMLButtonElement>();
  let importOpen = $state(false);
  let pickerOpen = $state(false);
  let exporting = $state(false);
  let importing = $state(false);

  // ── inline edit (v1.3 EntriesTable) ──────────────────────────────

  async function openEditor(id: string, field: EditField, text?: string, original?: string, invalid = false) {
    const e = $month?.entries.find((x) => x.id === id);
    if (!e) return;
    selectedId.set(id);
    editText = text ?? e[field];
    editor = { id, field, original: original ?? e[field], invalid };
    await tick();
    editorEl?.focus();
    editorEl?.select();
  }

  /** Close the editor; true when it is closed (saved, unchanged or reverted). */
  function closeEditor(commit: boolean, strict = false): Promise<boolean> {
    if (pending) return pending;
    if (!editor) return Promise.resolve(true);
    const p = doClose(commit, strict).finally(() => {
      if (pending === p) pending = null;
    });
    pending = p;
    return p;
  }

  async function doClose(commit: boolean, strict: boolean): Promise<boolean> {
    if (!editor) return true;
    const d = decideClose(editor.field, editText, editor.original, commit, strict);
    if (d.action === 'mark-invalid') {
      editor.invalid = true;
      editorEl?.focus();
      editorEl?.select();
      return false;
    }
    const ed = { ...editor, text: editText };
    editor = null;
    if (d.action === 'close') {
      if (d.note) toast(d.note, { tone: 'warning', ms: 4000 });
      return true;
    }
    saving = { id: ed.id, field: ed.field, value: d.value };
    let r;
    try {
      r = await runFlow((c) => api.update_entry_field(ed.id, ed.field, d.value, c));
    } finally {
      saving = null;
    }
    if (r.ok) {
      if (r.status === 'cancelled') {
        await openEditor(ed.id, ed.field, ed.text, ed.original);
        return false;
      }
      await refreshMonth({ select: ed.id, commit: false });
      return true;
    }
    if (r.status === 'error' && r.error.code === 'not_found') {
      await refreshMonth({ commit: false });
      return true;
    }
    if (r.status === 'invalid') {
      if (!strict) {
        toast('Invalid time, not saved', { tone: 'warning', ms: 4000 });
        return true;
      }
      await openEditor(ed.id, ed.field, ed.text, ed.original, true);
      return false;
    }
    await reportError(r, 'Could not save change');
    await openEditor(ed.id, ed.field, ed.text, ed.original);
    return false;
  }

  function focusRow(id: string | null) {
    if (!id) return;
    const tr = tbody?.querySelector<HTMLElement>(`tr[data-id="${CSS.escape(id)}"]`);
    tr?.focus({ preventScroll: true });
    tr?.scrollIntoView({ block: 'nearest' });
  }

  async function onEditorKey(e: KeyboardEvent) {
    if (!editor) return;
    if (e.key === 'Enter') {
      e.preventDefault();
      const id = editor.id;
      if (await closeEditor(true, true)) focusRow(id);
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const id = editor.id;
      if (await closeEditor(true)) focusRow(id);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      const id = editor.id;
      await closeEditor(false);
      focusRow(id);
    }
  }

  function onEditorInput() {
    if (editor?.invalid && parseEditor(editor.field, editText) !== null) editor.invalid = false;
  }

  function onEditorBlur() {
    // Deferred: keep the editor when the whole window lost focus (Alt+Tab).
    setTimeout(() => {
      if (!editor || pending) return;
      if (!document.hasFocus()) return;
      if (editorEl && document.activeElement === editorEl) return;
      void closeEditor(true);
    }, 10);
  }

  async function onCellClick(e: MouseEvent, id: string, field: EditField) {
    e.stopPropagation();
    if (editor && editor.id === id && editor.field === field) return;
    if (editor || pending) {
      if (!(await closeEditor(true))) return;
    }
    await openEditor(id, field);
  }

  // ── table selection / keys ───────────────────────────────────────

  function onRowClick(id: string) {
    if (editor && editor.id !== id) void closeEditor(true);
    selectedId.set(id);
  }

  function onRowDblClick(e: MouseEvent, id: string) {
    if ((e.target as HTMLElement).closest('.editable')) return;
    if ($selectedId === id) void editEntry();
  }

  function onRowKey(e: KeyboardEvent, id: string) {
    let next: string | null = null;
    if (e.key === 'ArrowDown') next = moveSelection(ids, id, 1);
    else if (e.key === 'ArrowUp') next = moveSelection(ids, id, -1);
    else if (e.key === 'Home' && !e.ctrlKey) next = ids[0] ?? null;
    else if (e.key === 'End' && !e.ctrlKey) next = ids[ids.length - 1] ?? null;
    else if (e.key === 'ArrowRight' && !e.ctrlKey) {
      e.preventDefault();
      (e.currentTarget as HTMLElement).querySelector<HTMLElement>('.editable button')?.focus();
      return;
    } else return;
    e.preventDefault();
    selectedId.set(next);
    focusRow(next);
  }

  function onCellKey(e: KeyboardEvent) {
    const btn = e.currentTarget as HTMLElement;
    const tr = btn.closest('tr');
    const all = [...(tr?.querySelectorAll<HTMLElement>('.editable button') ?? [])];
    const i = all.indexOf(btn);
    if (e.key === 'ArrowLeft' && !e.ctrlKey) {
      e.preventDefault();
      e.stopPropagation();
      (i > 0 ? all[i - 1] : tr)?.focus();
    } else if (e.key === 'ArrowRight' && !e.ctrlKey) {
      e.preventDefault();
      e.stopPropagation();
      all[i + 1]?.focus();
    }
  }

  function onWheel() {
    if (editor) void closeEditor(true);
  }

  $effect(() => {
    const id = $selectedId;
    void rows;
    if (!id) return;
    void tick().then(() => tbody?.querySelector(`tr[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' }));
  });

  // ── actions ──────────────────────────────────────────────────────

  async function addEntry() {
    if (!(await closeEditor(true))) return;
    const saved = await openSheet<{ entry: EntryRow | null; defaultDate: string }, EntryRow | null>(EntryModal, {
      entry: null,
      defaultDate: defaultEntryDate($viewMonth),
    });
    if (saved) await showEntry(saved);
  }

  async function editEntry() {
    if (!$selectedId) return;
    if (!(await closeEditor(true))) return;
    const entry = $month?.entries.find((e) => e.id === $selectedId);
    if (!entry) return;
    const saved = await openSheet<{ entry: EntryRow | null; defaultDate: string }, EntryRow | null>(EntryModal, {
      entry,
      defaultDate: entry.date,
    });
    if (saved) await showEntry(saved);
    focusRow($selectedId);
  }

  async function deleteEntry() {
    const id = $selectedId;
    if (!id) return;
    if (!(await closeEditor(true))) return;
    const after = moveSelection(ids, id, 1) === id ? moveSelection(ids, id, -1) : moveSelection(ids, id, 1);
    const r = await runFlow((c) => api.delete_entry(id, c));
    if (r.ok) {
      if (r.status !== 'ok' || !r.deleted) return;
      const deleted = r.deleted;
      const description = r.description ?? '';
      await refreshMonth({ select: after === id ? null : after });
      focusRow($selectedId);
      toast(`Deleted ${description}.`, { action: () => restore(deleted, description), tone: 'info' });
      return;
    }
    if (r.status === 'error' && r.error.code === 'not_found') await refreshMonth();
    await reportError(r, 'Could not delete');
  }

  async function restore(entry: WorkEntry, description: string): Promise<void> {
    const r = await api.restore_entry(entry);
    if (r.ok && r.status === 'saved' && r.entry) {
      await showEntry(r.entry);
      toast(`Restored ${description}.`, { tone: 'success', ms: 4000 });
      return;
    }
    await reportError(r, 'Could not restore');
    if (r.status === 'error' && r.error.code === 'internal') return;
    toast(`Could not restore ${description}.`, { action: () => restore(entry, description), label: 'Retry', tone: 'error' });
  }

  async function exportMonth() {
    if (exporting) return;
    if (!(await closeEditor(true))) return;
    exporting = true;
    try {
      const { year, month: m } = $viewMonth;
      const r = await api.export_month(year, m);
      if (r.ok) {
        if (r.status === 'saved' && r.path) toast(`Timesheet saved to:\n${r.path}`, { tone: 'success', ms: 6000 });
      } else if (r.status === 'error' && r.error.code === 'file_locked') {
        toast(r.error.message, { tone: 'error', ms: 12000 });
      } else {
        await reportError(r, 'Export failed');
      }
    } finally {
      exporting = false;
    }
  }

  async function importExcel() {
    if (importing) return;
    if (!(await closeEditor(true))) return;
    importing = true;
    try {
      const r = await api.import_excel();
      if (r.status === 'cancelled') return;
      if (!r.ok) {
        await reportError(r, 'Import failed');
        return;
      }
      await refreshMonth();
      await alert('Import complete', importSummary(r), r.errors.length ? 'warning' : 'success');
    } finally {
      importing = false;
    }
  }

  async function importOcr() {
    if (!(await closeEditor(true))) return;
    await openOcrImport();
  }

  const importItems = $derived<MenuItem[]>([
    { id: 'excel', label: 'From Excel…', icon: 'file' },
    ...($dlc.ocr_available ? [{ id: 'ocr', label: 'From image (OCR)…', icon: 'image' as const }] : []),
  ]);

  function onImportPick(id: string) {
    if (id === 'excel') void importExcel();
    else if (id === 'ocr') void importOcr();
  }

  async function openPicker() {
    if (!(await closeEditor(true))) return;
    pickerOpen = true;
  }

  async function pickMonth(y: number, m: number) {
    pickerOpen = false;
    await setViewMonth(y, m);
  }

  onMount(() => {
    const offs = [
      registerEditGuard(() => closeEditor(true)),
      registerCommand('entry.add', addEntry),
      registerCommand('entry.edit', editEntry),
      registerCommand('entry.delete', deleteEntry),
      registerCommand('export', exportMonth),
      registerCommand('import.menu', () => {
        importOpen = true;
      }),
      registerCommand('month.prev', () => void shiftMonth(-1)),
      registerCommand('month.next', () => void shiftMonth(1)),
      registerCommand('month.current', () => void goToCurrentMonth()),
    ];
    return () => offs.forEach((f) => f());
  });

  const TIME_FIELDS: EditField[] = ['time_in', 'time_out'];
  const hours = (e: EntryRow) => (e.minutes === null ? '—' : formatHM(e.minutes));
  const cellValue = (e: EntryRow, f: EditField) => (saving && saving.id === e.id && saving.field === f ? saving.value : e[f]);
</script>

<section class="entries glass" aria-labelledby="entries-title">
  <header class="head">
    <div class="title">
      <h2 id="entries-title">Shifts this month</h2>
      <button type="button" class="month-btn lg-gel" onclick={openPicker} aria-haspopup="dialog" aria-label="{label}, choose month">
        <Icon name="calendar" size={15} />
        <span>{label}</span>
        <Icon name="chevron-down" size={14} />
      </button>
      {#if $monthLoading}
        <span class="loading" transition:fade={{ duration: 150 }}><Spinner size={14} /></span>
      {/if}
    </div>
    <div class="actions">
      <Button
        variant="ghost"
        icon="download"
        iconRight="chevron-down"
        bind:el={importBtn}
        loading={importing}
        aria-haspopup="menu"
        aria-expanded={importOpen}
        tooltip={{ text: 'Import shifts', kbd: SHORTCUT_LABELS['import.menu'] }}
        onclick={() => (importOpen = !importOpen)}
      >
        Import
      </Button>
      <Button variant="primary" glow icon="plus" tooltip={{ text: 'Add a shift by hand', kbd: SHORTCUT_LABELS['entry.add'] }} onclick={addEntry}>
        Add entry
      </Button>
    </div>
  </header>

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="scroller" onwheel={onWheel}>
    {#if $monthError && !$month}
      <div class="state" role="alert" in:fade>
        <Icon name="error" size={28} />
        <p>{$monthError}</p>
        <Button variant="secondary" icon="refresh" onclick={() => refreshMonth()}>Try again</Button>
      </div>
    {:else if !$month}
      <div class="state" aria-busy="true"><Spinner size={22} /></div>
    {:else if !$month.entries.length}
      <div class="state empty" in:fly={{ y: 8 }}>
        <span class="empty-wizard" aria-hidden="true">
          <span class="empty-glow"></span>
          <img src={wizard} alt="" width="512" height="512" />
        </span>
        <p>{emptyText($month.label)}</p>
        <p class="hint">{EMPTY_HINT}</p>
      </div>
    {:else}
      <table data-entries-table aria-label="Shifts in {label}" aria-describedby="entries-total">
        <thead>
          <tr>
            <th scope="col" class="c-date">Date</th>
            <th scope="col" class="c-job">Job / Shift</th>
            <th scope="col" class="c-time">In</th>
            <th scope="col" class="c-time">Out</th>
            <th scope="col" class="c-hours">Hours</th>
          </tr>
        </thead>
        <tbody bind:this={tbody}>
          {#each rows as row (row.key)}
            {@const e = row.kind === 'entry' ? row.entry : null}
            <tr
              data-id={e?.id}
              class={e ? 'entry' : 'week'}
              class:selected={!!e && e.id === $selectedId}
              aria-selected={e ? e.id === $selectedId : undefined}
              tabindex={e ? (e.id === $selectedId || (!$selectedId && e.id === ids[0]) ? 0 : -1) : undefined}
              onclick={() => e && onRowClick(e.id)}
              ondblclick={(ev) => e && onRowDblClick(ev, e.id)}
              onkeydown={(ev) => e && onRowKey(ev, e.id)}
              animate:flip={{ duration: 260 }}
              in:fly={{ y: 10, duration: 260, delay: stagger(row.index) }}
              out:fade={{ duration: 140 }}
            >
              {#if e}
                <td class="c-date num">{e.display_date}</td>
                <td class="c-job"><span class="job">{e.job_shift || '—'}</span></td>
                {#each TIME_FIELDS as f (f)}
                  <td class="c-time editable" class:editing={editor?.id === e.id && editor.field === f}>
                    {#if editor && editor.id === e.id && editor.field === f}
                      <input
                        bind:this={editorEl}
                        bind:value={editText}
                        class="cell-input num"
                        class:invalid={editor?.invalid}
                        aria-invalid={editor?.invalid || undefined}
                        aria-label="{f === 'time_in' ? 'Time in' : 'Time out'}, {e.display_date}"
                        maxlength={8}
                        spellcheck="false"
                        autocomplete="off"
                        onkeydown={onEditorKey}
                        oninput={onEditorInput}
                        onblur={onEditorBlur}
                        onclick={(ev) => ev.stopPropagation()}
                      />
                    {:else}
                      <button
                        type="button"
                        class="cell-btn num"
                        class:saving={saving?.id === e.id && saving.field === f}
                        tabindex="-1"
                        aria-label="{f === 'time_in' ? 'Time in' : 'Time out'} {e[f] || 'empty'}, click to edit"
                        onclick={(ev) => onCellClick(ev, e.id, f)}
                        onkeydown={onCellKey}
                      >
                        {cellValue(e, f) || '—'}{#if f === 'time_out' && e.overnight}<span class="plus1" title="Ends the next day">+1</span>{/if}
                      </button>
                    {/if}
                  </td>
                {/each}
                <td class="c-hours num">{hours(e)}</td>
              {:else if row.kind === 'week'}
                <td colspan="5">
                  <span class="week-line">
                    <span class="week-pill num" aria-hidden="true">W{row.week.week}</span>
                    <span class="week-text num">{weekTotalText(row.week)}</span>
                  </span>
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <footer class="foot">
    <div class="sel-actions">
      <Button
        variant="secondary"
        size="sm"
        icon="edit"
        disabled={!selected}
        tooltip={{ text: 'Edit the selected shift', kbd: SHORTCUT_LABELS['entry.edit'] }}
        onclick={editEntry}
      >
        Edit
      </Button>
      <Button
        variant="danger"
        size="sm"
        icon="trash"
        disabled={!selected}
        tooltip={{ text: 'Delete the selected shift', kbd: SHORTCUT_LABELS['entry.delete'] }}
        onclick={deleteEntry}
      >
        Delete
      </Button>
    </div>
    <p id="entries-total" class="total num" aria-live="polite">
      <span class="total-label">Total:</span>
      <span class="total-hm">{formatHM($month?.total_minutes ?? 0)}</span>
      <span class="total-money">({formatMoney($month?.earnings ?? 0)})</span>
    </p>
    <Button
      variant="success"
      size="sm"
      icon="upload"
      loading={exporting}
      tooltip={{ text: 'Export this month to Excel', kbd: SHORTCUT_LABELS.export }}
      onclick={exportMonth}
    >
      Export to Excel
    </Button>
  </footer>
</section>

{#if importOpen}
  <Menu anchor={importBtn} items={importItems} label="Import" onselect={onImportPick} onclose={() => (importOpen = false)} />
{/if}

{#if pickerOpen}
  <MonthPicker year={$viewMonth.year} month={$viewMonth.month} onpick={pickMonth} oncancel={() => (pickerOpen = false)} />
{/if}

<style>
  .entries {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    border-radius: var(--radius-xl);
    overflow: hidden;
  }

  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px 16px;
    padding: 16px 18px 12px;
  }
  .title {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    flex-wrap: wrap;
  }
  h2 {
    margin: 0;
    font-size: var(--fs-lg);
    font-weight: 700;
    letter-spacing: -0.015em;
  }
  .month-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px 5px 9px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--glass-border);
    background: var(--neutral-fill);
    color: var(--text-muted);
    font: inherit;
    font-size: var(--fs-sm);
    font-weight: 550;
    cursor: pointer;
    transition:
      background var(--dur-fast) var(--ease-out),
      color var(--dur-fast) var(--ease-out),
      transform var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-fast) var(--ease-out);
  }
  .month-btn:hover {
    background: var(--neutral-fill-hover);
    color: var(--text);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px -8px var(--accent-glow);
  }
  .month-btn:active {
    transform: scale(0.97);
  }
  .loading {
    display: inline-flex;
    color: var(--text-muted);
  }
  .actions {
    display: flex;
    gap: 8px;
    margin-left: auto;
  }

  .scroller {
    flex: 1;
    min-height: 160px;
    overflow: auto;
    overscroll-behavior: contain;
    padding: 0 10px;
    scrollbar-gutter: stable;
  }

  table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: var(--fs-sm);
  }
  thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: 9px 10px;
    text-align: left;
    font-size: var(--fs-xs);
    font-weight: 650;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    background: var(--glass-fill-strong);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--divider);
  }
  th.c-time,
  th.c-hours,
  td.c-time,
  td.c-hours {
    text-align: center;
  }
  .c-date {
    width: 24%;
    white-space: nowrap;
  }
  .c-time {
    width: 15%;
  }
  .c-hours {
    width: 13%;
  }

  td {
    padding: 0 10px;
    height: 40px;
    border-bottom: 1px solid var(--divider);
  }
  tr.entry {
    cursor: default;
    outline: none;
    transition: background var(--dur-fast) var(--ease-out);
  }
  tr.entry:hover td {
    background: var(--row-hover);
  }
  tr.entry.selected td {
    background: var(--row-selected);
  }
  tr.entry.selected td:first-child {
    box-shadow: inset 3px 0 0 var(--accent);
  }
  tr.entry:focus-visible td {
    box-shadow: inset 0 2px 0 var(--focus-ring), inset 0 -2px 0 var(--focus-ring);
  }
  tr.entry:focus-visible td:first-child {
    box-shadow: inset 2px 0 0 var(--focus-ring), inset 0 2px 0 var(--focus-ring), inset 0 -2px 0 var(--focus-ring);
  }
  tr.entry:focus-visible td:last-child {
    box-shadow: inset -2px 0 0 var(--focus-ring), inset 0 2px 0 var(--focus-ring), inset 0 -2px 0 var(--focus-ring);
  }
  td:first-child {
    border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  }
  td:last-child {
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  }
  .c-job .job {
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text);
  }
  .c-hours {
    font-weight: 600;
  }

  td.editable {
    padding: 0 4px;
  }
  .cell-btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
    width: 100%;
    min-height: 30px;
    padding: 0 6px;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text);
    font: inherit;
    cursor: text;
    transition:
      background var(--dur-fast) var(--ease-out),
      border-color var(--dur-fast) var(--ease-out);
  }
  .cell-btn:hover {
    background: var(--field-bg);
    border-color: var(--field-border);
  }
  .cell-btn:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--focus-ring);
  }
  .cell-btn.saving {
    color: var(--text-muted);
    animation: pulse 900ms var(--ease-out) infinite alternate;
  }
  @keyframes pulse {
    to {
      opacity: 0.55;
    }
  }
  .plus1 {
    font-size: 0.72em;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: var(--radius-pill);
    color: var(--warning-text);
    background: color-mix(in srgb, var(--amber) 16%, transparent);
    transform: translateY(-4px);
  }
  .cell-input {
    width: 100%;
    min-height: 30px;
    padding: 0 6px;
    text-align: center;
    font: inherit;
    font-family: var(--font-mono);
    color: var(--text);
    background: var(--field-bg);
    border: 1px solid var(--accent);
    border-radius: var(--radius-sm);
    outline: none;
    box-shadow: 0 0 0 3px var(--focus-ring);
    transition:
      border-color var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-fast) var(--ease-out);
  }
  .cell-input.invalid {
    border-color: var(--danger);
    box-shadow: 0 0 0 3px var(--danger-glow);
    color: var(--danger-text);
  }

  tr.week td {
    height: 34px;
    border-bottom: 1px solid var(--divider);
  }
  .week-line {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
    color: var(--text-muted);
    font-size: var(--fs-xs);
    font-weight: 600;
  }
  .week-pill {
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    color: var(--accent-text);
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent) 28%, transparent);
  }

  .state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    min-height: 200px;
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
  }
  .state p {
    margin: 0;
    max-width: 34ch;
  }
  /* top of the splash art (bubble + wizard) in a glass-edged frame */
  .empty-wizard {
    position: relative;
    display: block;
    width: 168px;
    aspect-ratio: 1 / 0.68;
  }
  .empty-wizard img {
    position: relative;
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: 50% 0;
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    box-shadow: inset 0 1px 0 var(--glass-highlight), var(--shadow-md);
  }
  .empty-glow {
    position: absolute;
    inset: -28px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--accent-glow), transparent 70%);
    opacity: 0.6;
  }
  .state .hint {
    font-size: var(--fs-sm);
    color: var(--text-subtle);
  }

  .foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px 14px;
    padding: 12px 18px 14px;
    border-top: 1px solid var(--divider);
    background: var(--glass-fill);
  }
  .sel-actions {
    display: flex;
    gap: 8px;
  }
  .total {
    margin: 0 0 0 auto;
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: var(--fs-md);
  }
  .total-label {
    font-family: var(--font-ui);
    color: var(--text-muted);
    font-size: var(--fs-sm);
  }
  .total-hm {
    font-weight: 700;
  }
  .total-money {
    color: var(--text-muted);
  }

  @media (max-width: 560px) {
    .c-date {
      width: auto;
    }
    .c-job {
      display: none;
    }
    .total {
      margin-left: 0;
      width: 100%;
      order: -1;
    }
  }

  /* Liquid glass: sheen chip (its label is muted, so no clear tint), gel
     press, and a rim under the sticky header */
  :global(:root[data-glass='liquid']) .month-btn {
    background: linear-gradient(180deg, var(--lg-sheen), transparent 60%), var(--neutral-fill);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }
  :global(:root[data-glass='liquid']) .month-btn:hover {
    background: linear-gradient(180deg, var(--lg-sheen), transparent 60%), var(--neutral-fill-hover);
    box-shadow: inset 0 1px 0 var(--glass-highlight), 0 6px 18px -8px var(--accent-glow);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .month-btn.lg-gel {
    transition:
      background var(--dur-fast) var(--ease-out),
      color var(--dur-fast) var(--ease-out),
      transform var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-fast) var(--ease-out),
      scale 460ms var(--lg-spring);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .month-btn.lg-gel:active {
    transform: none;
    scale: 1.06 0.94;
    transition-duration: var(--dur-fast), var(--dur-fast), var(--dur-fast), var(--dur-fast), 90ms;
  }
  :global(:root[data-glass='liquid']) thead th {
    box-shadow: inset 0 -1px 0 var(--lg-rim-weak);
  }
</style>
