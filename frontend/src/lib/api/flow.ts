import { confirm } from '../stores/confirm';
import type { ConfirmList, Result } from './types';

const MAX_ROUNDS = 12;

/** Runs a confirm-protocol call: on `needs_confirm` shows the modal, appends the
 *  answer and re-calls with all answers so far, until a final result.
 *  `preset` answers questions the caller already knows the answer to. */
export async function runFlow<R extends Result<any>>(
  call: (confirm: ConfirmList) => Promise<R>,
  preset: ConfirmList = [],
): Promise<R> {
  const answers: ConfirmList = [...preset];
  for (let round = 0; ; round++) {
    const result: Result<any> = await call(answers.length ? [...answers] : (undefined as unknown as ConfirmList));
    if (result.status !== 'needs_confirm' || round >= MAX_ROUNDS) return result as R;
    const req = result.confirm;
    const choice = await confirm(req);
    answers.push(req.token === undefined ? { kind: req.kind, choice } : { kind: req.kind, choice, token: req.token });
  }
}
