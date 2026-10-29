import { get, writable } from 'svelte/store';
import { api } from '../api/bridge';
import { onEvent } from '../api/events';
import type { MonthData } from '../api/types';
import { addMonths, fromIsoDate } from '../time';
import { viewMonth } from './app';
import { commitEdits } from './editGuard';

export { viewMonth };

export const month = writable<MonthData | null>(null);
export const selectedId = writable<string | null>(null);
export const monthLoading = writable(false);
/** Set when list_month failed; views show it instead of the table. */
export const monthError = writable<string | null>(null);

let seq = 0;

/** Re-read the viewed month; keeps (or sets) the selection. An open inline
 *  edit is committed first (v1.3 refresh); if that fails nothing reloads.
 *  `commit: false` is only for the editor's own post-save reload. */
export async function refreshMonth(opts: { select?: string | null; commit?: boolean } = {}): Promise<void> {
  if (opts.commit !== false && !(await commitEdits())) return;
  const mySeq = ++seq;
  const { year, month: m } = get(viewMonth);
  monthLoading.set(true);
  const r = await api.list_month(year, m);
  if (mySeq !== seq) return;
  monthLoading.set(false);
  if (!r.ok || !r.data) {
    monthError.set(r.status === 'error' ? r.error.message : r.message ?? 'Could not load shifts');
    return;
  }
  monthError.set(null);
  month.set(r.data);
  if (opts.select !== undefined) selectedId.set(opts.select);
  else {
    const sel = get(selectedId);
    if (sel && !r.data.entries.some((e) => e.id === sel)) selectedId.set(null);
  }
}

/** Show another month. Commits an open inline edit first; false = stayed. */
export async function setViewMonth(year: number, m: number): Promise<boolean> {
  const cur = get(viewMonth);
  if (cur.year === year && cur.month === m) return true;
  if (!(await commitEdits())) return false;
  viewMonth.set({ year, month: m });
  selectedId.set(null);
  await refreshMonth({ commit: false });
  return true;
}

export function shiftMonth(delta: number): Promise<boolean> {
  const cur = get(viewMonth);
  const next = addMonths(cur.year, cur.month, delta);
  return setViewMonth(next.year, next.month);
}

export function goToCurrentMonth(): Promise<boolean> {
  const now = new Date();
  return setViewMonth(now.getFullYear(), now.getMonth() + 1);
}

/** Jump to the entry's month and select it (after save / stop / restore). */
export async function showEntry(entry: { id: string; date: string }): Promise<void> {
  if (!(await commitEdits())) return;
  const d = fromIsoDate(entry.date);
  if (d) viewMonth.set({ year: d.getFullYear(), month: d.getMonth() + 1 });
  await refreshMonth({ select: entry.id, commit: false });
}

onEvent('data:changed', () => void refreshMonth());
