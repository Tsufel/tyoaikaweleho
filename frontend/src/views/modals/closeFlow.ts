import { api, runFlow } from '../../lib/api';
import { reportError } from '../../lib/stores/confirm';
import { commitEdits } from '../../lib/stores/editGuard';
import { focusTopModal } from '../../lib/stores/modals';
import { refreshTimer, setTimer } from '../../lib/stores/timer';
import { toast } from '../../lib/stores/toasts';
import '../timer/setup';

let busy = false;

/** §6.8: App calls this on `close:requested`. Python quits on its own when the
 *  flow ends ok/saved/discarded; anything else leaves the window (and the
 *  running shift) as it was. */
export async function handleCloseRequest(): Promise<void> {
  if (busy) return;
  if (focusTopModal()) return;
  busy = true;
  try {
    if (!(await commitEdits())) return;
    const r = await runFlow((c) => api.close_app(c));
    if (r.timer) setTimer(r.timer);
    if (r.status !== 'error') return;
    if (r.error.code === 'stale') {
      await refreshTimer();
      toast('The shift changed in the meantime — the window stays open.', { tone: 'warning', ms: 5000 });
      return;
    }
    if (!r.timer) await refreshTimer();
    await reportError(r, 'Could not save shift');
  } finally {
    busy = false;
  }
}
