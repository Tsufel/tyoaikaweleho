import type { Component } from 'svelte';
import { get, writable } from 'svelte/store';
import type { ConfirmChoices, ConfirmDetails, ConfirmKind, ConfirmOption, ConfirmRequest, Result } from '../api/types';
import { errorLogPath } from './app';

export type DialogIcon = 'info' | 'question' | 'warning' | 'error' | 'success';

/** Anything ChoiceModal can show; a ConfirmRequest is one. */
export interface ChoiceRequest {
  kind?: ConfirmKind | string;
  title: string;
  message: string;
  options: ConfirmOption[];
  default: string;
  cancel: string;
  icon: DialogIcon;
  token?: string;
  details?: ConfirmDetails;
}

/** Props a registered confirm renderer receives. It must call `onchoose`
 *  exactly once (Escape / close → request.cancel). Wrap it in `lib/ui/Modal`. */
export interface ConfirmRendererProps<K extends ConfirmKind = ConfirmKind> {
  request: ConfirmRequest<K>;
  onchoose: (choice: ConfirmChoices[K]) => void;
}

/** Props of a sheet opened with openSheet: the component calls `onclose(result)`. */
export type SheetProps<P, T> = P & { onclose: (result: T) => void };

export type DialogItem =
  | { id: number; type: 'choice'; request: ChoiceRequest; renderer: Component<any> | null; resolve: (choice: string) => void }
  | { id: number; type: 'sheet'; component: Component<any>; props: Record<string, unknown>; resolve: (result: unknown) => void };

const items = writable<DialogItem[]>([]);
/** Rendered by lib/ui/ConfirmHost (mounted once in App). */
export const dialogs = { subscribe: items.subscribe };

const renderers = new Map<string, Component<any>>();
let nextId = 1;

/** Use a custom modal for one confirm kind (e.g. over_24h → StopConfirm). */
export function registerConfirmRenderer<K extends ConfirmKind>(
  kind: K,
  component: Component<ConfirmRendererProps<K>>,
): () => void {
  renderers.set(kind, component as Component<any>);
  return () => {
    if (renderers.get(kind) === (component as Component<any>)) renderers.delete(kind);
  };
}

function remove(id: number) {
  items.update((all) => all.filter((d) => d.id !== id));
}

/** Show a choice modal; resolves with an option id (cancel on Escape). */
export function choose(req: ChoiceRequest): Promise<string> {
  return new Promise((resolve) => {
    const id = nextId++;
    const renderer = req.kind ? renderers.get(req.kind) ?? null : null;
    items.update((all) => [
      ...all,
      { id, type: 'choice', request: req, renderer, resolve: (c) => { remove(id); resolve(c); } },
    ]);
  });
}

/** Answer a Python confirm request (see api/flow.runFlow). */
export function confirm<K extends ConfirmKind>(req: ConfirmRequest<K>): Promise<ConfirmChoices[K]> {
  return choose(req as ChoiceRequest) as Promise<ConfirmChoices[K]>;
}

/** Open a custom modal component; resolves with what it passes to `onclose`. */
export function openSheet<P extends Record<string, unknown>, T>(
  component: Component<SheetProps<P, T>>,
  props: P,
): Promise<T> {
  return new Promise((resolve) => {
    const id = nextId++;
    items.update((all) => [
      ...all,
      {
        id,
        type: 'sheet',
        component: component as Component<any>,
        props,
        resolve: (r) => { remove(id); resolve(r as T); },
      },
    ]);
  });
}

export function alert(title: string, message: string, icon: DialogIcon = 'info'): Promise<void> {
  return choose({
    title, message, icon,
    options: [{ id: 'ok', label: 'OK', variant: 'primary' }],
    default: 'ok', cancel: 'ok',
  }).then(() => undefined);
}

export async function askYesNo(
  title: string,
  message: string,
  opts: { icon?: DialogIcon; default?: 'yes' | 'no'; yes?: string; no?: string; danger?: boolean } = {},
): Promise<boolean> {
  const c = await choose({
    title, message, icon: opts.icon ?? 'question',
    options: [
      { id: 'yes', label: opts.yes ?? 'Yes', variant: opts.danger ? 'danger' : 'primary' },
      { id: 'no', label: opts.no ?? 'No', variant: 'neutral' },
    ],
    default: opts.default ?? 'yes', cancel: 'no',
  });
  return c === 'yes';
}

/** Yes → true, No → false, Cancel/Escape → null. */
export async function askYesNoCancel(title: string, message: string, icon: DialogIcon = 'question'): Promise<boolean | null> {
  const c = await choose({
    title, message, icon,
    options: [
      { id: 'yes', label: 'Yes', variant: 'primary' },
      { id: 'no', label: 'No', variant: 'neutral' },
      { id: 'cancel', label: 'Cancel', variant: 'neutral' },
    ],
    default: 'yes', cancel: 'cancel',
  });
  return c === 'yes' ? true : c === 'no' ? false : null;
}

let internalShowing = false;

/** Show a failed result: `internal` gets the generic box (one at a time),
 *  others their message under `title`. No-op for ok/needs_confirm. */
export async function reportError(r: Result<any>, title = 'Something went wrong'): Promise<void> {
  if (r.status === 'invalid') {
    await alert(title === 'Something went wrong' ? 'Invalid input' : title, r.message, 'error');
    return;
  }
  if (r.status !== 'error') return;
  if (r.error.code === 'internal') {
    if (internalShowing) return;
    internalShowing = true;
    try {
      await alert(
        'Something went wrong',
        `Something went wrong: ${r.error.message}\n\nYour saved shifts are not affected. The details were written to:\n${get(errorLogPath)}`,
        'error',
      );
    } finally {
      internalShowing = false;
    }
    return;
  }
  await alert(title, r.error.message || r.message || 'The action could not be completed.', 'error');
}
