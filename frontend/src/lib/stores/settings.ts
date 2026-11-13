import { get, writable } from 'svelte/store';
import { api } from '../api/bridge';
import { onEvent } from '../api/events';
import type { DlcStatus, Settings, UiPrefs } from '../api/types';
import { toast } from './toasts';

export const DEFAULT_UI_PREFS: UiPrefs = {
  lulz: false,
  reduce_effects: false,
  lulz_sound: false,
  liquid_glass: false,
  target_hours: 8,
  pet: 'off',
  pet_name: '',
  pet_hint_seen: false,
  pet_skin: 'classic',
  zoom: 100,
};

export const DEFAULT_SETTINGS: Settings = {
  appearance: 'System',
  default_start_time: '09:30',
  pay_rate: 20,
  pay_rate_text: '20',
  default_job_shift: '',
  export_format: 'Simple',
  export_include_pay: false,
  export_include_names: false,
  employee_name: '',
  manager_name: '',
  rounding: { enabled: false, mode: 'nearest', step: 30 },
  ui_prefs: { ...DEFAULT_UI_PREFS },
};

export const settings = writable<Settings>(DEFAULT_SETTINGS);
export const shifts = writable<string[]>([]);
export const dlc = writable<DlcStatus>({
  state: 'missing',
  version: null,
  update_version: null,
  message: null,
  ocr_available: false,
});

let uiPrefsSeq = 0;
let uiPrefsInFlight = 0;
/** ui_prefs as Python last confirmed them, and which save that reply belonged to. */
let confirmedPrefs: UiPrefs | null = null;
let confirmedSeq = 0;

export function applySettings(s: Settings, sh?: string[]): void {
  const ui_prefs = { ...DEFAULT_UI_PREFS, ...s.ui_prefs };
  settings.set({ ...s, ui_prefs });
  confirmedPrefs = ui_prefs;
  confirmedSeq = uiPrefsSeq;
  if (sh) shifts.set(sh);
}

/** Instant toggles (Lulz / Lulz sound / Reduce effects / Liquid glass / target hours), outside the Save button. */
export async function saveUiPrefs(prefs: Partial<UiPrefs>): Promise<boolean> {
  const seq = ++uiPrefsSeq;
  const before = get(settings);
  // with nothing in flight, the store is what Python holds
  if (uiPrefsInFlight === 0) {
    confirmedPrefs = before.ui_prefs;
    confirmedSeq = seq - 1;
  }
  settings.set({ ...before, ui_prefs: { ...before.ui_prefs, ...prefs } });
  uiPrefsInFlight++;
  let r: Awaited<ReturnType<typeof api.save_ui_prefs>>;
  try {
    r = await api.save_ui_prefs(prefs);
  } finally {
    uiPrefsInFlight--;
  }
  const ok = r.ok && !!r.settings;
  // replies can overlap (a held zoom key) and arrive out of order; only the
  // newest reply seen so far says what Python holds
  if (ok && seq >= confirmedSeq) {
    confirmedPrefs = { ...DEFAULT_UI_PREFS, ...r.settings!.ui_prefs };
    confirmedSeq = seq;
  }
  // once nothing is in flight, show exactly what was saved: a failed save's
  // optimistic value must not survive, and no older reply may roll back a newer one
  if (uiPrefsInFlight === 0 && confirmedPrefs) {
    settings.set({ ...get(settings), ui_prefs: confirmedPrefs });
  }
  if (ok) return true;
  toast(r.message ?? (r.status === 'error' ? r.error.message : 'Could not save the setting'), { tone: 'error', ms: 6000 });
  return false;
}

onEvent('dlc:status', (s) => dlc.set(s));
