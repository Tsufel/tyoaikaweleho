import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fakeApi = vi.hoisted(() => ({
  install_update: vi.fn(),
  open_download_page: vi.fn(),
}));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));

const { dialogs } = await import('../src/lib/stores/confirm');
const { installUpdate, openDownloadPage } = await import('../src/views/settings/updateFlow');

const URL = 'https://github.com/Tsufel/tyoaikaweleho/releases/latest';
const okR = { ok: true, status: 'ok' };
const errR = (code: string, message: string) => ({ ok: false, status: 'error', error: { code, message } });

// ── dialog driver: answers each dialog with the next scripted choice ──
let script: string[] = [];
let shown: { title: string; message: string; options: string[] }[] = [];
const seen = new Set<number>();
dialogs.subscribe((items) => {
  for (const d of items) {
    if (d.type !== 'choice' || seen.has(d.id)) continue;
    seen.add(d.id);
    shown.push({ title: d.request.title, message: d.request.message, options: d.request.options.map((o) => o.label) });
    const choice = script.shift() ?? d.request.cancel;
    queueMicrotask(() => d.resolve(choice));
  }
});

beforeEach(() => {
  script = [];
  shown = [];
  fakeApi.install_update.mockReset();
  fakeApi.open_download_page.mockReset().mockResolvedValue(okR);
});
afterEach(() => vi.restoreAllMocks());

describe('openDownloadPage', () => {
  it('opens the page without a dialog when it works', async () => {
    await openDownloadPage();
    expect(fakeApi.open_download_page).toHaveBeenCalledOnce();
    expect(shown).toEqual([]);
  });

  it('shows the URL to copy when the browser cannot be opened', async () => {
    fakeApi.open_download_page.mockResolvedValue(errR('internal', `Could not open:\n${URL}\n\nno association`));
    await openDownloadPage();
    expect(shown).toHaveLength(1);
    expect(shown[0].title).toBe('Could not open the download page');
    expect(shown[0].message).toContain(URL);
  });
});

describe('failed update', () => {
  const failure = errR('update_failed', "The update could not be installed:\n\nGitHub's security certificate could not be verified");

  it('offers the download page and opens it on yes', async () => {
    fakeApi.install_update.mockResolvedValue(failure);
    script = ['yes'];
    await installUpdate('2.0.1');
    expect(shown).toHaveLength(1);
    expect(shown[0].title).toBe('Update failed');
    expect(shown[0].message).toContain('security certificate');
    expect(shown[0].options).toEqual(['Open download page', 'Close']);
    expect(fakeApi.open_download_page).toHaveBeenCalledOnce();
  });

  it('leaves the browser alone on close', async () => {
    fakeApi.install_update.mockResolvedValue(failure);
    script = ['no'];
    await installUpdate('2.0.1');
    expect(shown).toHaveLength(1);
    expect(fakeApi.open_download_page).not.toHaveBeenCalled();
  });
});
