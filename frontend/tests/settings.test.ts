import { get } from 'svelte/store';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { DlcStatus, Settings, UiPrefs } from '../src/lib/api/types';
import { lulz, lulzSound } from '../src/lib/stores/motion';
import { DEFAULT_SETTINGS, DEFAULT_UI_PREFS, applySettings, settings } from '../src/lib/stores/settings';
import {
  checkOutcome,
  clampTarget,
  dlcInstalledMessage,
  dlcNewerNote,
  dlcView,
  draftFromForm,
  fieldOf,
  formatTarget,
  formFromSettings,
  isDirty,
  payPreview,
  SHORTCUTS,
  upToDateMessage,
} from '../src/views/settings/settingsLogic';

const S: Settings = {
  appearance: 'System',
  default_start_time: '09:30',
  pay_rate: 20.5,
  pay_rate_text: '20.5',
  default_job_shift: 'Morning',
  export_format: 'Simple',
  export_include_pay: false,
  ui_prefs: { lulz: true, reduce_effects: false, lulz_sound: false, target_hours: 8 },
};

const dlc = (p: Partial<DlcStatus>): DlcStatus => ({
  state: 'missing',
  version: null,
  update_version: null,
  message: null,
  ocr_available: false,
  ...p,
});

describe('settings form', () => {
  it('builds the form from settings using pay_rate_text', () => {
    const f = formFromSettings(S);
    expect(f.pay_rate).toBe('20.5');
    expect(f.target_hours).toBe(8);
  });

  it('dirty tracking ignores surrounding whitespace', () => {
    const a = formFromSettings(S);
    expect(isDirty(a, { ...a, pay_rate: ' 20.5 ' })).toBe(false);
    expect(isDirty(a, { ...a, pay_rate: '21' })).toBe(true);
    expect(isDirty(a, { ...a, appearance: 'Dark' })).toBe(true);
    expect(isDirty(a, { ...a, target_hours: 7.5 })).toBe(true);
    expect(isDirty(a, { ...a, export_include_pay: true })).toBe(true);
  });

  it('draft keeps instantly-saved prefs from live settings', () => {
    const f = { ...formFromSettings(S), pay_rate: ' 20,50 ', target_hours: 6 };
    const live = { ...S, ui_prefs: { ...S.ui_prefs, lulz: false, reduce_effects: true, lulz_sound: true } };
    const d = draftFromForm(f, live);
    expect(d.pay_rate).toBe('20,50');
    expect(d.ui_prefs).toEqual({ lulz: false, reduce_effects: true, lulz_sound: true, target_hours: 6 });
  });

  it('clamps and formats the daily target', () => {
    expect(clampTarget(0)).toBe(1);
    expect(clampTarget(30)).toBe(24);
    expect(clampTarget(7.3)).toBe(7.5);
    expect(clampTarget(Number.NaN)).toBe(8);
    expect(formatTarget(8)).toBe('8 h');
    expect(formatTarget(7.5)).toBe('7 h 30 min');
  });

  it('maps server field names', () => {
    expect(fieldOf('pay_rate')).toBe('pay_rate');
    expect(fieldOf('target_hours')).toBe('target_hours');
    expect(fieldOf('appearance')).toBeNull();
    expect(fieldOf(undefined)).toBeNull();
  });

  it('previews pay in euros', () => {
    expect(payPreview(20, 8)).toBe('€160.00 for a 8 h day');
    expect(payPreview(null, 8)).toBeNull();
  });
});

describe('lulz sound', () => {
  const withPrefs = (p: Partial<UiPrefs>) => applySettings({ ...S, ui_prefs: { ...S.ui_prefs, ...p } });
  afterEach(() => {
    vi.unstubAllGlobals();
    applySettings(DEFAULT_SETTINGS);
  });

  it('defaults off, also when a stored prefs object predates the key', () => {
    expect(DEFAULT_UI_PREFS.lulz_sound).toBe(false);
    applySettings({ ...S, ui_prefs: { lulz: true } as UiPrefs });
    expect(get(settings).ui_prefs.lulz_sound).toBe(false);
    expect(get(lulz)).toBe(true);
    expect(get(lulzSound)).toBe(false);
  });

  it('is on only when both lulz and lulz_sound are on', () => {
    withPrefs({ lulz: false, lulz_sound: true });
    expect(get(lulzSound)).toBe(false);
    withPrefs({ lulz: true, lulz_sound: false });
    expect(get(lulzSound)).toBe(false);
    withPrefs({ lulz: true, lulz_sound: true });
    expect(get(lulzSound)).toBe(true);
  });

  it('is off when reduce effects blocks lulz', () => {
    withPrefs({ lulz: true, lulz_sound: true, reduce_effects: true });
    expect(get(lulz)).toBe(false);
    expect(get(lulzSound)).toBe(false);
  });

  it('is off under system reduced motion', () => {
    withPrefs({ lulz: true, lulz_sound: true });
    expect(get(lulzSound)).toBe(true);
    const mq = { matches: true, addEventListener: () => {}, removeEventListener: () => {} };
    vi.stubGlobal('matchMedia', () => mq);
    expect(get(lulz)).toBe(false);
    expect(get(lulzSound)).toBe(false);
  });
});

describe('update check', () => {
  it('reports an available update', () => {
    const s = checkOutcome({ current: '2.0.0', latest: '2.1.0', available: true }, null, '2.0.0');
    expect(s).toEqual({ kind: 'available', version: '2.1.0', current: '2.0.0' });
  });

  it('is up to date, with a DLC note when a newer DLC exists', () => {
    const d = { current: '1.0', latest: '1.1', available: true };
    const s = checkOutcome({ current: '2.0.0', latest: '2.0.0', available: false }, d, '2.0.0', 42);
    expect(s).toEqual({ kind: 'uptodate', version: '2.0.0', dlcNote: dlcNewerNote(d), at: 42 });
    expect(dlcNewerNote(d)).toContain('v1.1');
    expect(upToDateMessage('2.0.0', null)).toBe("You're up to date (v2.0.0).");
    expect(dlcNewerNote(null)).toBeNull();
  });

  it('falls back to the installed version', () => {
    const s = checkOutcome({ current: null, latest: null, available: false }, null, '1.9.0', 1);
    expect(s.kind === 'uptodate' && s.version).toBe('1.9.0');
  });
});

describe('DLC store states', () => {
  it('missing: install', () => {
    const v = dlcView(dlc({}));
    expect(v.primary?.action).toBe('install');
    expect(v.canRemove).toBe(false);
    expect(v.tone).toBe('idle');
  });

  it('installed: remove only', () => {
    const v = dlcView(dlc({ state: 'ok', version: '1.2', ocr_available: true }));
    expect(v.primary).toBeNull();
    expect(v.canRemove).toBe(true);
    expect(v.badge).toBe('v1.2');
  });

  it('installed with update: update', () => {
    const v = dlcView(dlc({ state: 'ok', version: '1.2', update_version: '1.3' }));
    expect(v.tone).toBe('update');
    expect(v.primary).toEqual({ action: 'update', label: 'Update to v1.3' });
  });

  it('incompatible: update with warning', () => {
    const v = dlcView(dlc({ state: 'incompatible', version: '0.9', message: 'Too old.' }));
    expect(v.tone).toBe('warning');
    expect(v.primary?.action).toBe('update');
    expect(v.detail).toBe('Too old.');
    expect(v.canRemove).toBe(true);
  });

  it('install message mentions a missing checksum', () => {
    const ok = dlc({ state: 'ok', ocr_available: true });
    expect(dlcInstalledMessage(true, ok)).toContain('ready to use');
    expect(dlcInstalledMessage(true, ok)).not.toContain('checksum');
    expect(dlcInstalledMessage(false, ok)).toContain('checksum');
    expect(dlcInstalledMessage(true, dlc({ state: 'incompatible' }))).toContain("can't be used");
  });
});

it('shortcuts table lists the settings keys', () => {
  expect(SHORTCUTS.some((s) => s.keys.includes('Ctrl+S'))).toBe(true);
  expect(SHORTCUTS.some((s) => s.keys.includes('F5'))).toBe(true);
});
