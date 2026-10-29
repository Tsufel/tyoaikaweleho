import { get, writable } from 'svelte/store';
import { api } from '../api/bridge';
import type { Recovery, RecoveryResult } from '../api/types';
import { reportError } from './confirm';
import { showEntry, refreshMonth, setViewMonth } from './entries';
import { setTimer } from './timer';

/** Unsaved shift from a crash / "Close anyway" (§4.5, §6.3). App.svelte shows
 *  RecoverShiftModal while this is non-null (after intro + changelog); it is
 *  cleared only when the result says recovery is gone (saved/resumed/discarded). */
export const pendingRecovery = writable<Recovery | null>(null);

/** Re-offer recovery, e.g. after timer_start returned error/recovery_pending.
 *  Without an argument the pending session is re-read through bootstrap(). */
export async function offerRecovery(rec?: Recovery | null): Promise<void> {
  if (rec) return pendingRecovery.set(rec);
  const r = await api.bootstrap();
  if (r.ok) {
    pendingRecovery.set(r.data.recovery);
    setTimer(r.data.timer);
  }
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
  if (r.status === 'saved' && r.entry) await showEntry(r.entry);
  else if (r.timer?.running && r.timer.start_iso) {
    const [y, m] = r.timer.start_iso.split('-').map(Number);
    if (!(await setViewMonth(y, m))) await refreshMonth();
  } else await refreshMonth();
}
