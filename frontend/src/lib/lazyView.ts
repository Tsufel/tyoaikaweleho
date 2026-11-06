import { get } from 'svelte/store';
import { api } from './api/bridge';
import { commitEdits } from './stores/editGuard';
import { modalOpen } from './stores/modals';
import { toast } from './stores/toasts';

/** sessionStorage: when a failed chunk last reloaded the page. */
const RELOAD_KEY = 'weleho-chunk-reload';
/** A chunk failing again within this long after that reload is a real fault. */
export const RELOAD_WINDOW_MS = 2 * 60_000;
/** How long the log line gets to reach Python before the page goes. */
const LOG_WAIT_MS = 500;

/** Swappable in tests (jsdom can't reload). */
export const page = { reload: () => window.location.reload() };

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function logLine(line: string): Promise<unknown> {
  try {
    return Promise.resolve(api.log_client_error(line.slice(0, 2000))).catch(() => undefined);
  } catch {
    return Promise.resolve(); // logging is best effort
  }
}

/** Log to error.log that a lazy chunk didn't load. */
export function logChunkFailure(chunk: string, err: unknown): void {
  void logLine(`Could not load the ${chunk} chunk: ${errText(err)}`);
}

/** reloading: the page is going. busy: a dialog or an unsaved edit is open, so
 *  it didn't (try again once it's closed). failed: it reloaded for this
 *  recently, or can't remember doing so: show the error instead of looping. */
export type ReloadOutcome = 'reloading' | 'busy' | 'failed';

/** A lazy chunk that won't load mostly means this page is an older UI than the
 *  files on disk (Weleho was updated while it ran, or an old index.html came
 *  from the cache): its chunk names are gone. Reload once to get the current
 *  UI, but never over an open dialog or an edit that can't be saved. */
export async function reloadForStaleChunk(chunk: string, err: unknown): Promise<ReloadOutcome> {
  const now = Date.now();
  try {
    const last = Number(sessionStorage.getItem(RELOAD_KEY)) || 0;
    if (now >= last && now - last < RELOAD_WINDOW_MS) return 'failed';
  } catch {
    return 'failed'; // no way to remember the reload: never risk a loop
  }
  if (get(modalOpen) > 0 || !(await commitEdits())) return 'busy';
  try {
    sessionStorage.setItem(RELOAD_KEY, String(now));
  } catch {
    return 'failed';
  }
  const line = `Could not load the ${chunk} chunk, reloading the page: ${errText(err)}`;
  await Promise.race([logLine(line), new Promise((r) => setTimeout(r, LOG_WAIT_MS))]);
  page.reload();
  return 'reloading';
}

/** Import a lazy route chunk; when it fails, reload once (the promise then
 *  never settles, so a spinner stays up while the page goes), else rethrow. */
export async function importOrReload<T>(chunk: string, load: () => Promise<T>): Promise<T> {
  try {
    return await load();
  } catch (err) {
    if ((await reloadForStaleChunk(chunk, err)) === 'reloading') return new Promise<never>(() => {});
    throw err;
  }
}

/** Load a lazy view chunk. When it can't load, reload the page once (see
 *  reloadForStaleChunk); if that didn't help, say so in a toast and log why to
 *  error.log, instead of the click doing nothing. Resolves to null then. */
export async function loadView<T>(
  chunk: string,
  label: string,
  load: () => Promise<{ default: T }>,
): Promise<T | null> {
  try {
    return (await load()).default;
  } catch (err) {
    const outcome = await reloadForStaleChunk(chunk, err);
    if (outcome === 'reloading') return null;
    logChunkFailure(chunk, err);
    toast(
      outcome === 'busy'
        ? `Couldn't open ${label} right now. Close what's open, then try again.`
        : `Couldn't open ${label}. If this keeps happening, reinstall Weleho.`,
      { tone: 'error', undo: false },
    );
    return null;
  }
}
