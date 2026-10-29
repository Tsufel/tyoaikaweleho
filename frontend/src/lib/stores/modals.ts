import { derived, get, writable } from 'svelte/store';

/** Ids of open modals, bottom → top. Only the top one handles keys. */
const stack = writable<number[]>([]);
const elements = new Map<number, () => void>();
let nextId = 1;

export const modalStack = { subscribe: stack.subscribe };
/** Number of open modals (0 = idle; shortcuts are gated on this). */
export const modalOpen = derived(stack, (s) => s.length);
export const topModal = derived(stack, (s) => s[s.length - 1] ?? null);

/** Called by Modal on mount; `focus` brings that modal to attention. */
export function pushModal(focus: () => void): { id: number; release: () => void } {
  const id = nextId++;
  elements.set(id, focus);
  stack.update((s) => [...s, id]);
  return {
    id,
    release: () => {
      elements.delete(id);
      stack.update((s) => s.filter((x) => x !== id));
    },
  };
}

export const isModalOpen = () => get(stack).length > 0;

/** Focus (and nudge) the top modal — close requested while a dialog waits. */
export function focusTopModal(): boolean {
  const s = get(stack);
  const fn = s.length ? elements.get(s[s.length - 1]) : undefined;
  fn?.();
  return !!fn;
}
