import type { Api, ApiMethod, ErrorResult } from './types';

type RawApi = Record<string, (...args: unknown[]) => Promise<unknown>>;

declare global {
  interface Window {
    pywebview?: { api: RawApi };
    chrome?: { webview?: unknown };
  }
}

let backend: RawApi | null = null;
let usingMock = false;

/** Inside WebView2 (pywebview) we never fall back to the mock. */
const inWebView = () => typeof window !== 'undefined' && !!window.chrome?.webview;

function forceMock(): boolean {
  try {
    return new URLSearchParams(location.search).has('mock');
  } catch {
    return false;
  }
}

function pywebviewApi(): RawApi | null {
  const api = window.pywebview?.api;
  return api && typeof api.bootstrap === 'function' ? api : null;
}

async function loadMock(): Promise<RawApi> {
  const { createMockApi } = await import('./mock');
  usingMock = true;
  return createMockApi() as unknown as RawApi;
}

async function resolveBackend(): Promise<RawApi> {
  if (forceMock() && !inWebView()) return loadMock();
  const existing = pywebviewApi();
  if (existing) return existing;
  return new Promise<RawApi>((resolve) => {
    let done = false;
    const finish = (api: RawApi) => {
      if (done) return;
      done = true;
      window.removeEventListener('pywebviewready', onReady);
      resolve(api);
    };
    const onReady = () => {
      const api = pywebviewApi();
      if (api) finish(api);
    };
    window.addEventListener('pywebviewready', onReady);
    // pywebview can finish injecting between our check and the listener
    const poll = setInterval(() => {
      const api = pywebviewApi();
      if (api) {
        clearInterval(poll);
        finish(api);
      }
    }, 50);
    if (!inWebView()) {
      setTimeout(() => {
        if (done) return;
        clearInterval(poll);
        loadMock().then(finish);
      }, 350);
    } else {
      setTimeout(() => {
        if (!done) console.error('pywebview API still not ready after 10 s');
      }, 10_000);
    }
  });
}

/** Resolves once the backend (pywebview or mock) can take calls. */
export const ready: Promise<void> = (typeof window === 'undefined'
  ? Promise.resolve(null as unknown as RawApi)
  : resolveBackend()
).then((api) => {
  backend = api;
});

export const isMock = () => usingMock;

function internalError(err: unknown): ErrorResult {
  const message = err instanceof Error ? err.message : String(err);
  return { ok: false, status: 'error', error: { code: 'internal', message } };
}

async function call(name: string, args: unknown[]): Promise<unknown> {
  await ready;
  // pywebview JSON-encodes the args: trailing undefined would arrive as None
  let n = args.length;
  while (n > 0 && args[n - 1] === undefined) n--;
  const fn = backend?.[name];
  if (typeof fn !== 'function') return internalError(`API method ${name} is missing`);
  try {
    const result = await fn.apply(backend, args.slice(0, n));
    return result ?? { ok: true, status: 'ok' };
  } catch (err) {
    return internalError(err);
  }
}

/** Typed API proxy: every call waits for `ready` and never rejects. */
export const api: Api = new Proxy({} as Api, {
  get(_target, prop) {
    if (typeof prop !== 'string' || prop === 'then') return undefined;
    return (...args: unknown[]) => call(prop as ApiMethod, args);
  },
});
