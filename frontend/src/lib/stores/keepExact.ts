import { api } from '../api/bridge';
import type { RoundedSave } from '../api/types';
import { reportError } from './confirm';
import { refreshMonth, showEntry } from './entries';
import { toast, type ToastTone } from './toasts';

/** "Rounded from 09:07–16:41", or "" when the save wasn't rounded. */
export function roundedNote(rounded: RoundedSave | undefined): string {
  return rounded ? `Rounded from ${rounded.before.time_in}–${rounded.before.time_out}` : '';
}

/** The saved-shift toast: `head`, then `after` (an overlap warning) as its
 *  own sentence. When Settings → Round shift times changed the times it says
 *  from what, before `after`, and its Keep exact (or Ctrl+Z) puts them back. */
export function savedShiftToast(
  head: string,
  rounded: RoundedSave | undefined,
  tone: ToastTone,
  ms: number,
  after = '',
): void {
  const parts = [head.replace(/\.$/, ''), roundedNote(rounded), after].filter(Boolean);
  const message = parts.length > 1 ? parts.join('. ') : head;
  if (!rounded) {
    toast(message, { tone, ms });
    return;
  }
  toast(message, {
    tone,
    ms: Math.max(ms, 10000),
    label: 'Keep exact',
    action: () => keepExact(rounded),
  });
}

/** Undo the rounding of a just-saved timer shift, only while the shift is
 *  still exactly as that save left it. */
export async function keepExact(rounded: RoundedSave): Promise<void> {
  const r = await api.revert_entry(rounded.before, rounded.token);
  const exact = `${rounded.before.time_in}–${rounded.before.time_out}`;
  if (r.ok && r.status === 'saved') {
    await showEntry(r.entry ?? rounded.before);
    toast(`Kept the exact times ${exact}.`, { tone: 'success', ms: 4000 });
    return;
  }
  if (r.status === 'error' && r.error.code === 'stale') {
    toast('That shift was changed again since, so its times were left as they are.', { tone: 'warning', ms: 6000 });
    return;
  }
  if (r.status === 'error' && r.error.code === 'not_found') {
    await refreshMonth({ commit: false });
    toast('That shift no longer exists.', { tone: 'warning', ms: 6000 });
    return;
  }
  await reportError(r, 'Could not keep the exact times');
}
