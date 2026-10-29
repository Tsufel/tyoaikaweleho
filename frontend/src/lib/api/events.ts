import { EVENT_CHANNEL, type EventDetail, type EventMap, type EventName } from './types';

type Handler<N extends EventName> = (payload: EventMap[N]) => void;

const handlers = new Map<EventName, Set<Handler<any>>>();
let listening = false;

function listen() {
  if (listening || typeof window === 'undefined') return;
  listening = true;
  window.addEventListener(EVENT_CHANNEL, (ev) => {
    const detail = (ev as CustomEvent<EventDetail>).detail;
    if (!detail || typeof detail.name !== 'string') return;
    for (const fn of handlers.get(detail.name) ?? []) {
      try {
        fn(detail.payload);
      } catch (err) {
        console.error(`weleho event ${detail.name}:`, err);
      }
    }
  });
}

/** Subscribe to a Python → JS event. Returns an unsubscribe function. */
export function onEvent<N extends EventName>(name: N, fn: Handler<N>): () => void {
  listen();
  let set = handlers.get(name);
  if (!set) handlers.set(name, (set = new Set()));
  set.add(fn);
  return () => set!.delete(fn);
}

/** Dispatch an event on the shared channel (used by the mock and tests). */
export function emitEvent<N extends EventName>(name: N, payload: EventMap[N]): void {
  listen();
  window.dispatchEvent(new CustomEvent(EVENT_CHANNEL, { detail: { name, payload } }));
}
