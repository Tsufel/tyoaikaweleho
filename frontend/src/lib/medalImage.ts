import { api } from './api/bridge';

/** How long to wait before the one retry (a refused connection gets a moment). */
export const RETRY_DELAY_MS = 300;

/** Shown when a medal can't load at all: a plain grey coin with a "?", in
 *  place of the browser's broken-image box. */
export const MEDAL_PLACEHOLDER =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
      '<circle cx="32" cy="32" r="28" fill="#8a8f98" fill-opacity=".35" stroke="#8a8f98" stroke-width="3"/>' +
      '<text x="32" y="43" text-anchor="middle" font-family="sans-serif" font-size="30" font-weight="700" fill="#8a8f98">?</text>' +
      '</svg>',
  );

/** URLs already written to error.log this session (one line each is enough). */
const logged = new Set<string>();

/** Tests only. */
export function resetMedalLog(): void {
  logged.clear();
}

function logFailure(src: string): void {
  if (logged.has(src)) return;
  logged.add(src);
  try {
    void Promise.resolve(
      api.log_client_error(`Medal image failed to load: ${src || '(no url)'} (after one retry)`),
    ).catch(() => undefined);
  } catch {
    // logging is best effort
  }
}

/** The same file under a new cache key, so a bad copy in WebView2's cache is
 *  skipped (the server ignores the query). */
export function retryUrl(src: string, stamp: number = Date.now()): string {
  return `${src}${src.includes('?') ? '&' : '?'}r=${stamp}`;
}

/** Svelte action that owns a medal <img>'s src. A medal that fails to load is
 *  tried once more under a fresh URL; if that fails too it shows a placeholder
 *  and the URL goes to error.log.
 *
 *  2.1.7: a colleague's Achievements showed every hidden ("???") Silver card as
 *  a broken image. All of a tier's hidden cards share one file, so one failed
 *  load (a bad cached copy, or a refused connection) broke them all, for good:
 *  nothing ever asked for the file again. */
export function medalImg(node: HTMLImageElement, src: string) {
  let current = src;
  let tries = 0;
  let gaveUp = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function giveUp() {
    logFailure(current);
    gaveUp = true;
    node.src = MEDAL_PLACEHOLDER;
  }

  function show(url: string) {
    tries = 0;
    gaveUp = false;
    clearTimeout(timer);
    current = url;
    if (url) node.src = url;
    else giveUp();
  }

  function onError() {
    if (gaveUp) return; // the placeholder itself: never loop
    tries += 1;
    if (tries === 1) {
      const wanted = current;
      timer = setTimeout(() => {
        if (current === wanted) node.src = retryUrl(wanted);
      }, RETRY_DELAY_MS);
    } else {
      giveUp();
    }
  }

  node.addEventListener('error', onError);
  show(src);

  return {
    update(next: string) {
      if (next !== current) show(next);
    },
    destroy() {
      clearTimeout(timer);
      node.removeEventListener('error', onError);
    },
  };
}
