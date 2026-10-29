import { get, writable } from 'svelte/store';
import { api, runFlow } from '../../lib/api';
import type { DlcStatus } from '../../lib/api/types';
import { bootstrap } from '../../lib/stores/app';
import { alert, openSheet, reportError } from '../../lib/stores/confirm';
import { modalOpen } from '../../lib/stores/modals';
import { pendingRecovery } from '../../lib/stores/recovery';
import { dlc } from '../../lib/stores/settings';
import { toast } from '../../lib/stores/toasts';
import { dlcInstalledMessage, type DlcAction } from './settingsLogic';
import UpdateAvailableModal from './UpdateAvailableModal.svelte';

/** Blocking progress overlay rendered by UpdateFlow (can't be cancelled, as in v1.3). */
export interface Overlay {
  kind: 'update' | 'dlc';
  title: string;
  message: string;
  note?: string;
}

export const overlay = writable<Overlay | null>(null);
/** DLC action in progress (Settings disables the DLC buttons meanwhile). */
export const dlcBusy = writable<DlcAction | null>(null);

const installedVersion = () => get(bootstrap)?.version ?? '';

// ── App update ───────────────────────────────────────────────────

let prompting = false;
let lastPrompt: { version: string; at: number } | null = null;
let failureShown = false;

/** Resolves once nothing else is on screen: no intro, modal or pending recovery. */
function whenQuiet(): Promise<void> {
  const quiet = () =>
    get(modalOpen) === 0 && !get(pendingRecovery) && !document.querySelector('.intro') && !get(overlay);
  if (quiet()) return Promise.resolve();
  return new Promise((resolve) => {
    const id = setInterval(() => {
      if (quiet()) {
        clearInterval(id);
        resolve();
      }
    }, 400);
  });
}

/** "Version X is available …" — one prompt at a time (startup check and the
 *  manual check can both land here). */
export async function promptUpdate(version: string, current = installedVersion(), opts: { wait?: boolean } = {}): Promise<void> {
  if (prompting || get(overlay)) return;
  if (lastPrompt && lastPrompt.version === version && Date.now() - lastPrompt.at < 5000) return;
  prompting = true;
  try {
    if (opts.wait !== false) await whenQuiet();
    const yes = await openSheet<{ version: string; current: string }, boolean>(UpdateAvailableModal, { version, current });
    lastPrompt = { version, at: Date.now() };
    if (!yes) return;
  } finally {
    prompting = false;
  }
  await installUpdate(version);
}

function showInstalling(version: string) {
  overlay.set({
    kind: 'update',
    title: `Updating to v${version}`,
    message: 'Downloading update…',
    note: 'The app will close and relaunch automatically. Your running shift is kept.',
  });
}

async function updateFailed(message: string) {
  if (failureShown) return;
  failureShown = true;
  overlay.set(null);
  await alert('Update failed', message, 'error');
}

export async function installUpdate(version: string): Promise<void> {
  failureShown = false;
  showInstalling(version);
  const r = await api.install_update();
  if (r.ok) return; // the installer closes the app
  if (r.status === 'error' && r.error.code === 'not_frozen') {
    overlay.set(null);
    await alert('Update', r.error.message || 'Updates can only be installed from the installed app, not when running from source.');
    return;
  }
  if (r.status === 'error' && r.error.code === 'update_failed') {
    await updateFailed(r.error.message);
    return;
  }
  overlay.set(null);
  failureShown = true;
  await reportError(r, 'Update failed');
}

/** Event handlers (UpdateFlow wires them). */
export const updateEvents = {
  available: (p: { version: string; current: string }) => void promptUpdate(p.version, p.current),
  installing: (p: { version: string }) => {
    if (get(overlay)?.kind !== 'update') showInstalling(p.version);
  },
  failed: (p: { message: string }) => {
    if (get(overlay)?.kind === 'update') void updateFailed(p.message);
  },
  dlcUpdate: (p: { version: string }) => dlc.update((d) => (d.state === 'missing' ? d : { ...d, update_version: p.version })),
};

// ── DLC ──────────────────────────────────────────────────────────

function dlcError(r: { status: string; error?: { message: string }; message?: string }, fallback: string): string {
  return r.error?.message || r.message || fallback;
}

export async function installDlc(action: 'install' | 'update' = 'install'): Promise<DlcStatus | null> {
  if (get(dlcBusy)) return null;
  dlcBusy.set(action);
  overlay.set({
    kind: 'dlc',
    title: action === 'update' ? 'Updating DLC' : 'Installing DLC',
    message: 'Downloading image_ocr.py…',
    note: 'This usually takes a few seconds.',
  });
  try {
    const r = await api.dlc_install();
    overlay.set(null);
    if (r.ok) {
      dlc.set(r.dlc);
      await alert(action === 'update' ? 'DLC updated' : 'DLC installed', dlcInstalledMessage(r.verified, r.dlc), r.dlc.state === 'incompatible' ? 'warning' : 'success');
      return r.dlc;
    }
    if (r.status === 'error' && r.error.code === 'internal') await reportError(r);
    else await alert('Install failed', dlcError(r, 'The DLC could not be installed.'), 'error');
    if (r.dlc) dlc.set(r.dlc);
    return null;
  } finally {
    overlay.set(null);
    dlcBusy.set(null);
  }
}

export async function removeDlc(): Promise<DlcStatus | null> {
  if (get(dlcBusy)) return null;
  dlcBusy.set('remove');
  try {
    const r = await runFlow((c) => api.dlc_remove(c));
    if (r.status === 'cancelled') return null;
    if (r.ok) {
      dlc.set(r.dlc);
      toast('Image OCR DLC removed. Your saved entries are not affected.', { tone: 'success', ms: 5000 });
      return r.dlc;
    }
    if (r.status === 'error' && r.error.code === 'internal') await reportError(r);
    else await alert('Remove failed', dlcError(r, 'The DLC could not be removed.'), 'error');
    if (r.dlc) dlc.set(r.dlc);
    return null;
  } finally {
    dlcBusy.set(null);
  }
}
