type Guard = () => Promise<boolean> | boolean;

const guards = new Set<Guard>();

/** Register a function that commits an open inline edit; it resolves false
 *  when the edit could not be saved (the edit stays open). */
export function registerEditGuard(fn: Guard): () => void {
  guards.add(fn);
  return () => guards.delete(fn);
}

/** Commit open edits before leaving the month / opening a modal / closing.
 *  false → abandon the action. */
export async function commitEdits(): Promise<boolean> {
  for (const fn of [...guards]) {
    try {
      if (!(await fn())) return false;
    } catch (err) {
      console.error('edit guard failed', err);
      return false;
    }
  }
  return true;
}
