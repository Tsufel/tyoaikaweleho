import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BackupInfo, Settings } from '../src/lib/api/types';

const fakeApi = vi.hoisted(() => ({
  list_backups: vi.fn(),
  backup_now: vi.fn(),
  restore_backup: vi.fn(),
  open_data_folder: vi.fn(),
  get_timer: vi.fn(),
  get_error_log_info: vi.fn(),
  save_error_log: vi.fn(),
  reveal_error_log: vi.fn(),
}));

vi.mock('../src/lib/api/bridge', () => ({ api: fakeApi, ready: Promise.resolve(), isMock: true }));

const { dialogs } = await import('../src/lib/stores/confirm');
const { route } = await import('../src/lib/stores/app');
const { settings, shifts } = await import('../src/lib/stores/settings');
const { clearToasts, toasts } = await import('../src/lib/stores/toasts');
const { createMockApi } = await import('../src/lib/api/mock');
const flow = await import('../src/views/settings/dataFlow');

// ── dialog driver: answers each dialog with the next scripted choice ──
let script: string[] = [];
let shown: { title: string; message: string }[] = [];
const seen = new Set<number>();
dialogs.subscribe((items) => {
  for (const d of items) {
    if (seen.has(d.id)) continue;
    seen.add(d.id);
    if (d.type === 'choice') {
      shown.push({ title: d.request.title, message: d.request.message });
      const choice = script.shift() ?? d.request.cancel;
      queueMicrotask(() => d.resolve(choice));
    }
  }
});

const info = (p: Partial<BackupInfo>): BackupInfo => ({
  name: 'data-2026-09-22.json',
  kind: 'daily',
  saved_at: '2026-09-22T17:05:00',
  size: 1200,
  ok: true,
  entries: 12,
  last_entry_date: '2026-09-22',
  ...p,
});

const S: Settings = {
  appearance: 'Dark',
  default_start_time: '07:00',
  pay_rate: 15,
  pay_rate_text: '15',
  default_job_shift: 'Restored',
  export_format: 'Simple',
  export_include_pay: false,
  export_include_names: false,
  employee_name: '',
  manager_name: '',
  rounding: { enabled: false, mode: 'nearest', step: 30 },
  ui_prefs: { lulz: false, reduce_effects: false, lulz_sound: false, liquid_glass: false, target_hours: 8, pet: 'off', pet_name: '', pet_hint_seen: false, pet_skin: 'classic', zoom: 100 },
};
const TIMER = { running: false } as never;

const needsConfirm = {
  ok: false,
  status: 'needs_confirm',
  confirm: {
    kind: 'restore_backup',
    title: 'Restore backup',
    message: 'Replace your shifts and settings…?',
    options: [
      { id: 'restore', label: 'Restore', variant: 'danger' },
      { id: 'cancel', label: 'Cancel', variant: 'neutral' },
    ],
    default: 'cancel',
    cancel: 'cancel',
    icon: 'warning',
    token: 'tok',
  },
};

beforeEach(() => {
  script = [];
  shown = [];
  clearToasts();
  route.set('settings');
  for (const f of Object.values(fakeApi)) f.mockReset();
  fakeApi.list_backups.mockResolvedValue({ ok: true, status: 'ok', backups: [info({})], data_dir: 'D', backups_dir: 'D\\backups' });
});
afterEach(() => vi.restoreAllMocks());

describe('Your data: text', () => {
  it('summarises the backups', () => {
    expect(flow.backupStatus([])).toMatch(/^No backups yet/);
    expect(flow.backupStatus([info({ kind: 'bak' })])).toBe('1 backup. No daily snapshot yet.');
    expect(flow.backupStatus([info({ kind: 'bak' }), info({ name: 'b' })])).toBe('2 backups · last snapshot Tue 22 Sep 2026, 17:05');
  });

  it('describes one backup, and an unreadable one', () => {
    expect(flow.backupDetail(info({}))).toBe('12 shifts · up to Tue 22 Sep 2026');
    expect(flow.backupDetail(info({ entries: 1, last_entry_date: null }))).toBe('1 shift');
    expect(flow.backupDetail(info({ ok: false, entries: null }))).toMatch(/can't be restored/);
    expect(flow.formatSavedAt('nonsense')).toBe('nonsense');
  });
});

describe('Your data: actions', () => {
  it('loads the list', async () => {
    await flow.loadBackups();
    expect(get(flow.backups)).toHaveLength(1);
    expect(get(flow.backupsDir)).toBe('D\\backups');
    expect(get(flow.dataBusy)).toBeNull();
  });

  it('restores after the user says yes, then applies settings and leaves Settings', async () => {
    fakeApi.restore_backup.mockImplementation(async (_name: string, confirm?: unknown[]) => {
      if (!confirm) return needsConfirm;
      return {
        ok: true,
        status: 'saved',
        message: 'Restored the backup from 2026-09-22.',
        restored: 'data-2026-09-22.json',
        safety_copy: 'pre-restore-20260923-100000.json',
        settings: S,
        shifts: ['Restored'],
        timer: TIMER,
        backups: [info({})],
      };
    });
    script = ['restore'];
    expect(await flow.restoreBackup('data-2026-09-22.json')).toBe(true);
    expect(shown[0].title).toBe('Restore backup');
    expect(fakeApi.restore_backup).toHaveBeenLastCalledWith('data-2026-09-22.json', [
      { kind: 'restore_backup', choice: 'restore', token: 'tok' },
    ]);
    expect(get(settings).default_job_shift).toBe('Restored');
    expect(get(shifts)).toEqual(['Restored']);
    expect(get(route)).toBe('main');
    expect(get(toasts).map((t) => t.message)).toContain('Restored the backup from 2026-09-22.');
  });

  it('cancel leaves everything alone', async () => {
    fakeApi.restore_backup.mockImplementation(async (_n: string, c?: unknown[]) =>
      c ? { ok: true, status: 'cancelled' } : needsConfirm,
    );
    script = ['cancel'];
    expect(await flow.restoreBackup('data-2026-09-22.json')).toBe(false);
    expect(get(route)).toBe('settings');
    expect(get(flow.dataBusy)).toBeNull();
  });

  it('a backup that went away reloads the list', async () => {
    fakeApi.restore_backup.mockResolvedValue({ ok: false, status: 'invalid', field: 'name', message: 'That backup no longer exists.' });
    expect(await flow.restoreBackup('gone.json')).toBe(false);
    expect(shown[0].message).toBe('That backup no longer exists.');
    await vi.waitFor(() => expect(fakeApi.list_backups).toHaveBeenCalled());
    expect(get(route)).toBe('settings');
  });

  it('Back up now with nothing saved says so instead of a toast', async () => {
    fakeApi.backup_now.mockResolvedValue({ ok: true, status: 'ok', message: 'Nothing to back up yet', backup: null, backups: [] });
    expect(await flow.backupNow()).toBeNull();
    expect(shown).toEqual([{ title: 'Nothing to back up', message: 'Nothing to back up yet' }]);
    expect(get(toasts)).toHaveLength(0);
  });

  it('Back up now toasts the new copy', async () => {
    fakeApi.backup_now.mockResolvedValue({ ok: true, status: 'saved', message: 'Backed up to backups\\manual-1.json.', backup: 'manual-1.json', backups: [info({ kind: 'manual', name: 'manual-1.json' })] });
    expect(await flow.backupNow()).toBe('manual-1.json');
    expect(get(flow.backups)[0].kind).toBe('manual');
    expect(get(toasts)[0].message).toMatch(/manual-1/);
  });
});

describe('Your data: error log', () => {
  const LOG = { exists: true, size: 3412, entries: 2, last_at: '2026-09-22T17:05:00' };

  it('summarises the log', () => {
    expect(flow.errorLogStatus(null)).toBe('');
    expect(flow.errorLogStatus({ exists: false, size: 0, entries: 0, last_at: null })).toBe('No errors logged.');
    expect(flow.errorLogStatus(LOG)).toBe('2 errors logged · last Tue 22 Sep 2026, 17:05 · 3 KB');
    expect(flow.errorLogStatus({ ...LOG, entries: 1, size: 200 })).toBe('1 error logged · last Tue 22 Sep 2026, 17:05 · 200 bytes');
  });

  it('loads the info, and forgets it when that fails', async () => {
    fakeApi.get_error_log_info.mockResolvedValue({ ok: true, status: 'ok', path: 'D\\error.log', ...LOG });
    await flow.loadErrorLog();
    expect(get(flow.errorLog)).toEqual(LOG);
    fakeApi.get_error_log_info.mockRejectedValue(new Error('bridge gone'));
    await flow.loadErrorLog();
    expect(get(flow.errorLog)).toBeNull();
  });

  it('re-reads the log after an internal error while the card is open', async () => {
    const { reportError } = await import('../src/lib/stores/confirm');
    fakeApi.get_error_log_info.mockResolvedValue({ ok: true, status: 'ok', path: 'D\\error.log', ...LOG, entries: 0, exists: false });
    const stop = flow.watchErrorLog();
    await vi.waitFor(() => expect(get(flow.errorLog)?.entries).toBe(0));
    fakeApi.get_error_log_info.mockResolvedValue({ ok: true, status: 'ok', path: 'D\\error.log', ...LOG, entries: 1 });
    await reportError({ ok: false, status: 'error', message: 'boom', error: { code: 'internal', message: 'boom' } } as never);
    await vi.waitFor(() => expect(get(flow.errorLog)?.entries).toBe(1));
    stop();
    const calls = fakeApi.get_error_log_info.mock.calls.length;
    await reportError({ ok: false, status: 'error', message: 'boom', error: { code: 'internal', message: 'boom' } } as never);
    expect(fakeApi.get_error_log_info).toHaveBeenCalledTimes(calls);
  });

  it('saves a copy and offers Show in folder for that copy', async () => {
    const path = 'C:\\Docs\\Weleho error log.txt';
    fakeApi.save_error_log.mockResolvedValue({ ok: true, status: 'saved', path, ...LOG });
    fakeApi.reveal_error_log.mockResolvedValue({ ok: true, status: 'ok' });
    expect(await flow.saveErrorLog()).toBe(path);
    expect(get(flow.dataBusy)).toBeNull();
    expect(get(flow.errorLog)).toEqual(LOG);
    const t = get(toasts)[0];
    expect(t.message).toBe(`Error log saved to:\n${path}`);
    expect(t.label).toBe('Show in folder');
    await t.action!();
    expect(fakeApi.reveal_error_log).toHaveBeenCalledWith(true);
  });

  it('cancel saves nothing and says nothing', async () => {
    fakeApi.save_error_log.mockResolvedValue({ ok: true, status: 'cancelled' });
    expect(await flow.saveErrorLog()).toBeNull();
    expect(get(toasts)).toHaveLength(0);
    expect(shown).toEqual([]);
  });

  it('a failed save is reported', async () => {
    fakeApi.save_error_log.mockResolvedValue({
      ok: false,
      status: 'error',
      message: 'Could not save the error log',
      error: { code: 'save_failed', message: 'Could not save the error log' },
    });
    expect(await flow.saveErrorLog()).toBeNull();
    expect(shown[0].title).toBe('Could not save the error log');
    expect(get(toasts)).toHaveLength(0);
    expect(get(flow.dataBusy)).toBeNull();
  });

  it('Show in folder points at the log itself', async () => {
    fakeApi.reveal_error_log.mockResolvedValue({ ok: true, status: 'ok' });
    await flow.revealErrorLog();
    expect(fakeApi.reveal_error_log).toHaveBeenCalledWith(false);
  });
});

describe('mock api: your data', () => {
  it('tolerates being called with no args', async () => {
    const m = createMockApi() as unknown as Record<string, () => Promise<{ status: string }>>;
    for (const name of ['open_data_folder', 'list_backups', 'backup_now', 'restore_backup', 'get_error_log_info', 'save_error_log', 'reveal_error_log']) {
      await expect(m[name]()).resolves.toHaveProperty('status');
    }
  });

  it('restores a snapshot through the confirm protocol', async () => {
    const m = createMockApi();
    const list = await m.list_backups();
    if (!list.ok) throw new Error('list failed');
    const daily = list.backups.find((b) => b.kind === 'daily')!;
    const ask = await m.restore_backup(daily.name);
    expect(ask.status).toBe('needs_confirm');
    if (ask.status !== 'needs_confirm') return;
    const stale = await m.restore_backup(daily.name, [{ kind: 'restore_backup', choice: 'restore', token: 'old' }]);
    expect(stale.status).toBe('error');
    const r = await m.restore_backup(daily.name, [{ kind: 'restore_backup', choice: 'restore', token: ask.confirm.token }]);
    expect(r.status).toBe('saved');
    if (!r.ok) return;
    expect(r.safety_copy).toMatch(/^pre-restore-/);
    expect(r.backups[0].kind).toBe('pre-restore');
  });
});
