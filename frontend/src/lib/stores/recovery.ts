import { get, writable } from 'svelte/store';
import { api } from '../api/bridge';
import type { DataRecovery, Recovery, RecoveryResult } from '../api/types';
import { reportError } from './confirm';
import { showEntry, refreshMonth, setViewMonth } from './entries';
import { savedShiftToast } from './keepExact';
import { setTimer } from './timer';
import { toast } from './toasts';

/** Unsaved shift from a crash / "Close anyway" (§4.5, §6.3). App.svelte shows
 *  RecoverShiftModal while this is non-null (after intro + changelog); it is
 *  cleared only when the result says recovery is gone (saved/resumed/discarded). */
export const pendingRecovery = writable<Recovery | null>(null);

/** Re-offer recovery, e.g. after timer_start returned error/recovery_pending.
 *  Without an argument the pending session is re-read through get_recovery(),
 *  which (unlike bootstrap) writes nothing. */
export async function offerRecovery(rec?: Recovery | null): Promise<void> {
  if (rec) return pendingRecovery.set(rec);
  const r = await api.get_recovery();
  if (r.ok) {
    pendingRecovery.set(r.recovery);
    setTimer(r.timer);
    notifyDataRecovery(r.data_recovery);
  }
}

/** The sticky note shown after a backup stood in for data.json. */
export function dataRecoveryText(dr: DataRecovery): string {
  const what = dr.reason === 'missing' ? 'was missing' : 'was damaged';
  return (
    `Your hours file ${what} and has been restored from a backup (${dr.source.split(/[\\/]/).pop()}). ` +
    'Check your latest shifts.'
  );
}

/** Tell the user a damaged or missing data.json was replaced by a backup (sticky toast). */
export function notifyDataRecovery(dr: DataRecovery | null | undefined): void {
  if (!dr) return;
  toast(dataRecoveryText(dr), { tone: 'warning', ms: 0 });
}

/** Apply a recovery_resolve result: keeps the modal up on failure. */
export async function applyRecoveryResult(r: RecoveryResult): Promise<void> {
  if (r.timer) setTimer(r.timer);
  if (r.recovery !== undefined) pendingRecovery.set(r.recovery);
  else if (r.ok) pendingRecovery.set(null);

  if (!r.ok) {
    if (r.status === 'error') await reportError(r, 'Could not save the shift');
    return;
  }
  if (get(pendingRecovery)) return;
  if (r.status === 'saved' && r.overlap_warning) savedShiftToast('Shift saved', r.rounded, 'warning', 12000, r.overlap_warning);
  else if (r.status === 'saved' && r.rounded) savedShiftToast('Shift saved', r.rounded, 'success', 4000);
  if (r.status === 'saved' && r.entry) await showEntry(r.entry);
  else if (r.timer?.running && r.timer.start_iso) {
    const [y, m] = r.timer.start_iso.split('-').map(Number);
    if (!(await setViewMonth(y, m))) await refreshMonth();
  } else await refreshMonth();
}
