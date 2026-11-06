// Settings → Your data: the data folder, backups, Back up now and restore.
// Python decides what is a backup and checks the copy before anything is
// replaced; this module only shows the list and drives the confirm flow.
import { writable } from 'svelte/store';
import { api, runFlow } from '../../lib/api';
import type { BackupInfo, BackupKind } from '../../lib/api/types';
import { navigate } from '../../lib/stores/app';
import { alert, reportError } from '../../lib/stores/confirm';
import { applySettings } from '../../lib/stores/settings';
import { setTimer } from '../../lib/stores/timer';
import { toast } from '../../lib/stores/toasts';
import { fromIsoDate, strftime } from '../../lib/time';

export const backups = writable<BackupInfo[]>([]);
/** null until the first listing comes back (or when it failed). */
export const backupsDir = writable<string | null>(null);
export const backupsError = writable<string | null>(null);
/** What the card is doing; its buttons are disabled meanwhile. */
export const dataBusy = writable<null | 'list' | 'backup' | 'restore' | 'open'>(null);

export const KIND_LABELS: Record<BackupKind, string> = {
  bak: 'Last save',
  daily: 'Daily',
  manual: 'Manual',
  'pre-import': 'Before import',
  'pre-restore': 'Before restore',
  'pre-update': 'Before update',
};

/** 'Tue 23 Sep 2026, 10:00' from a local-naive ISO datetime. */
export function formatSavedAt(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : strftime(d, '%a %d %b %Y, %H:%M');
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** One line under the card title: how many copies there are and how fresh
 *  the newest automatic or manual one is. */
export function backupStatus(list: BackupInfo[]): string {
  if (!list.length) return 'No backups yet. One is made automatically the first time you save each day.';
  const snaps = list.filter((b) => b.kind === 'daily' || b.kind === 'manual');
  const count = plural(list.length, 'backup', 'backups');
  if (!snaps.length) return `${count}. No daily snapshot yet.`;
  return `${count} · last snapshot ${formatSavedAt(snaps[0].saved_at)}`;
}

/** '42 shifts · up to Tue 23 Sep 2026' or why it can't be restored. */
export function backupDetail(b: BackupInfo): string {
  if (!b.ok || b.entries === null) return "Can't be read, so it can't be restored.";
  const shifts = plural(b.entries, 'shift', 'shifts');
  const last = b.last_entry_date ? fromIsoDate(b.last_entry_date) : null;
  return last ? `${shifts} · up to ${strftime(last, '%a %d %b %Y')}` : shifts;
}

export async function loadBackups(): Promise<void> {
  dataBusy.update((b) => b ?? 'list');
  try {
    const r = await api.list_backups();
    if (r.ok) {
      backups.set(r.backups);
      backupsDir.set(r.backups_dir);
      backupsError.set(null);
    } else {
      backupsError.set(r.message ?? (r.status === 'error' ? r.error.message : 'Could not list the backups.'));
    }
  } finally {
    dataBusy.update((b) => (b === 'list' ? null : b));
  }
}

export async function openDataFolder(): Promise<void> {
  const r = await api.open_data_folder();
  if (!r.ok) await reportError(r, 'Could not open the data folder');
}

export async function backupNow(): Promise<string | null> {
  dataBusy.set('backup');
  try {
    const r = await api.backup_now();
    if (!r.ok) {
      await reportError(r, 'Could not back up');
      return null;
    }
    backups.set(r.backups);
    if (!r.backup) {
      await alert('Nothing to back up', r.message ?? 'No shifts have been saved yet.', 'info');
      return null;
    }
    toast(r.message ?? 'Backed up.', { tone: 'success', ms: 4000 });
    return r.backup;
  } finally {
    dataBusy.set(null);
  }
}

/** Ask, then swap the backup in (Python copies the current data aside
 *  first). On success the stores take the restored settings and the app
 *  goes back to the main view, since the settings form on screen is stale.
 *  The month view reloads itself on the data:changed event. */
export async function restoreBackup(name: string): Promise<boolean> {
  dataBusy.set('restore');
  try {
    const r = await runFlow((c) => api.restore_backup(name, c));
    if (r.status === 'cancelled' || r.status === 'needs_confirm') return false;
    if (!r.ok) {
      await reportError(r, 'Could not restore the backup');
      if (r.status === 'invalid' || (r.status === 'error' && r.error.code === 'stale')) void loadBackups();
      return false;
    }
    applySettings(r.settings, r.shifts);
    setTimer(r.timer);
    backups.set(r.backups);
    await navigate('main');
    toast(r.message ?? 'Backup restored.', { tone: 'success', ms: 8000 });
    return true;
  } finally {
    dataBusy.set(null);
  }
}
