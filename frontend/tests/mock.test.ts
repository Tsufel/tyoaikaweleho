import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createMockApi } from '../src/lib/api/mock';
import { onEvent } from '../src/lib/api/events';
import type { Api, ApiMethod } from '../src/lib/api/types';

// The browser mock (?mock) stands in for Python during UI work, so it must
// keep the same envelopes. Mirrors tests/test_api_contract.py's call list.
const CALLS: Partial<Record<ApiMethod, unknown[]>> = {
  bootstrap: [],
  frontend_ready: [],
  set_close_guard: [true],
  set_theme: ['Dark', true],
  log_client_error: ['boom', 'at x'],
  open_shifts_file: [],
  get_timer: [],
  timer_start: ['now', null, null, undefined],
  timer_stop: ['button', undefined],
  timer_discard: [undefined],
  recovery_resolve: ['discard', null, undefined],
  list_month: [2026, 9],
  get_entry: ['missing'],
  save_entry: [{ date: '2026-09-01', time_in: '08:00', time_out: '16:00', job_shift: 'Sales' }, undefined],
  update_entry_field: ['missing', 'time_in', '09:00', undefined],
  delete_entry: ['missing', undefined],
  restore_entry: [{ id: 'r1', date: '2026-09-02', job_shift: 'Sales', time_in: '08:00', time_out: '12:00' }],
  get_settings: [],
  save_settings: [{}],
  save_ui_prefs: [{ lulz: true }],
  add_job_shift: ['Night'],
  get_stats: ['2026-09-01', '2026-09-30', 'day'],
  get_stats_span: [],
  get_achievements: [],
  ack_achievements: [['first_shift']],
  get_pet_stats: [],
  export_month: [2026, 9],
  reveal_export: [],
  import_excel: [],
  ocr_pick_and_extract: [],
  ocr_save: [[]],
  check_updates: [],
  open_download_page: [],
  install_update: [],
  get_dlc_status: [],
  dlc_install: [],
  dlc_remove: [undefined],
  close_app: [undefined],
};

type Loose = Record<string, (...args: unknown[]) => Promise<any>>;

function setFlags(query: string) {
  window.history.replaceState(null, '', `/${query}`);
}

/** Run a mock call to completion: the mock sleeps to feel like a real backend. */
async function settle<T>(p: Promise<T>): Promise<T> {
  await vi.runAllTimersAsync();
  return p;
}

function checkEnvelope(name: string, r: any) {
  expect(r, name).toBeTypeOf('object');
  expect(typeof r.ok, `${name}: ok`).toBe('boolean');
  expect(typeof r.status, `${name}: status`).toBe('string');
  // Python's results go through JSON, so the mock's must survive it unchanged
  expect(JSON.parse(JSON.stringify(r)), `${name}: JSON round trip`).toEqual(r);
  if (r.status === 'error') {
    expect(r.ok, name).toBe(false);
    expect(typeof r.error?.code, `${name}: error.code`).toBe('string');
    expect(typeof r.error?.message, `${name}: error.message`).toBe('string');
  } else if (r.status === 'needs_confirm') {
    expect(r.ok, name).toBe(false);
    expect(typeof r.confirm?.kind, `${name}: confirm.kind`).toBe('string');
    expect(Array.isArray(r.confirm?.options), `${name}: confirm.options`).toBe(true);
  } else if (r.status === 'invalid') {
    expect(typeof r.field, `${name}: field`).toBe('string');
  } else {
    expect(r.ok, name).toBe(true);
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  setFlags('');
});

describe('mock API', () => {
  it('every method returns a JSON-safe result envelope', async () => {
    setFlags('?mock');
    const api = createMockApi() as unknown as Loose;
    const methods = Object.keys(api).filter((k) => typeof api[k] === 'function');
    expect(methods.length).toBeGreaterThan(30);
    for (const name of methods) {
      // A method added without args here is still called, with none.
      const args = CALLS[name as ApiMethod] ?? [];
      checkEnvelope(name, await settle(api[name](...args)));
    }
    for (const name of Object.keys(CALLS)) expect(methods, `mock lacks ${name}`).toContain(name);
  });

  it('&empty starts with no shifts', async () => {
    setFlags('?mock&empty');
    const api: Api = createMockApi();
    const now = new Date();
    const r = await settle(api.list_month(now.getFullYear(), now.getMonth() + 1));
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data.entries.length).toBe(0);
  });

  it('without &empty there is seeded history', async () => {
    setFlags('?mock');
    const api: Api = createMockApi();
    const r = await settle(api.get_stats_span());
    expect(r.ok && r.first).toBeTruthy();
  });

  it('&failsave makes saving a shift fail with save_failed', async () => {
    setFlags('?mock&empty&failsave'); // empty: no overlap question first
    const api: Api = createMockApi();
    const r = await settle(
      api.save_entry({ date: '2026-09-01', time_in: '08:00', time_out: '16:00', job_shift: 'Sales' }),
    );
    expect(r.status).toBe('error');
    if (r.status === 'error') expect(r.error.code).toBe('save_failed');
  });

  it('&update reports a newer version and announces it', async () => {
    setFlags('?mock&update');
    const seen: unknown[] = [];
    const off = onEvent('update:available', (p) => seen.push(p));
    try {
      const api: Api = createMockApi();
      const r = await settle(api.check_updates());
      expect(r.ok && r.app.available).toBe(true);
      expect(seen.length).toBeGreaterThan(0);
    } finally {
      off();
    }
  });

  it('&certfail turns update checks into a plain network error', async () => {
    setFlags('?mock&certfail');
    const api: Api = createMockApi();
    const r = await settle(api.check_updates());
    expect(r.status).toBe('error');
    if (r.status === 'error') expect(r.error.code).toBe('network');
  });

  it('save_ui_prefs takes a zoom level and rejects anything else', async () => {
    const api: Api = createMockApi();
    const ok = await settle(api.save_ui_prefs({ zoom: 120 }));
    expect(ok.ok && ok.settings.ui_prefs.zoom).toBe(120);
    for (const bad of [75, 115, 160]) {
      const r = await settle(api.save_ui_prefs({ zoom: bad }));
      expect(r.status).toBe('invalid');
    }
    const s = await settle(api.get_settings());
    expect(s.ok && s.settings.ui_prefs.zoom).toBe(120);
  });

  it('&zoom=130 seeds the UI zoom; a bad one is 100', async () => {
    setFlags('?mock&zoom=130');
    let r = await settle(createMockApi().get_settings());
    expect(r.ok && r.settings.ui_prefs.zoom).toBe(130);
    setFlags('?mock&zoom=125');
    r = await settle(createMockApi().get_settings());
    expect(r.ok && r.settings.ui_prefs.zoom).toBe(100);
  });

  it('&lulz&glass&skin=neon seed the UI prefs', async () => {
    setFlags('?mock&lulz&glass&skin=neon&pet=wizard');
    const api: Api = createMockApi();
    const r = await settle(api.get_settings());
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.settings.ui_prefs).toMatchObject({ lulz: true, liquid_glass: true, pet: 'wizard', pet_skin: 'neon' });
    }
  });
});
