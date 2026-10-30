import { derived, get, writable } from 'svelte/store';

export type ToastTone = 'info' | 'success' | 'warning' | 'error';

export interface Toast {
  id: number;
  message: string;
  tone: ToastTone;
  /** Action button (Undo / Retry); Ctrl+Z runs the newest one. */
  action?: () => void | Promise<void>;
  label?: string;
  /** Ctrl+Z may run the action (false for plain links such as "View"). */
  undo: boolean;
  ms: number;
}

export interface ToastOptions {
  action?: () => void | Promise<void>;
  label?: string;
  /** Visible time; default 8000 (the v1.3 undo window). 0 = until dismissed. */
  ms?: number;
  tone?: ToastTone;
  /** Default true: the action is an undo/retry Ctrl+Z can run. */
  undo?: boolean;
}

const MAX_TOASTS = 4;
let nextId = 1;
const list = writable<Toast[]>([]);

export const toasts = { subscribe: list.subscribe };

export function toast(message: string, opts: ToastOptions = {}): number {
  const t: Toast = {
    id: nextId++,
    message,
    tone: opts.tone ?? 'info',
    action: opts.action,
    label: opts.action ? opts.label ?? 'Undo' : undefined,
    undo: opts.undo ?? true,
    ms: opts.ms ?? 8000,
  };
  list.update((all) => [...all, t].slice(-MAX_TOASTS));
  return t.id;
}

export function dismiss(id: number): void {
  list.update((all) => all.filter((t) => t.id !== id));
}

export function clearToasts(): void {
  list.set([]);
}

/** True while a toast with an action (Undo/Retry) is on screen. */
export const undoAvailable = derived(list, (all) => all.some((t) => t.action && t.undo));

/** Ctrl+Z: run the newest toast action. Returns false when none is visible. */
export function runUndo(): boolean {
  const all = get(list);
  for (let i = all.length - 1; i >= 0; i--) {
    const t = all[i];
    if (t.action && t.undo) {
      dismiss(t.id);
      void t.action();
      return true;
    }
  }
  return false;
}

/** Run a toast's action from its button. */
export function runToastAction(id: number): void {
  const t = get(list).find((x) => x.id === id);
  if (!t?.action) return;
  dismiss(id);
  void t.action();
}
