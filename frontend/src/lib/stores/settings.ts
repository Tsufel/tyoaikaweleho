import { get, writable } from 'svelte/store';
import { api } from '../api/bridge';
import { onEvent } from '../api/events';
import type { DlcStatus, Settings, UiPrefs } from '../api/types';
import { toast } from './toasts';

export const DEFAULT_UI_PREFS: UiPrefs = { lulz: false, reduce_effects: false, lulz_sound: false, liquid_glass: false, target_hours: 8 };

export const DEFAULT_SETTINGS: Settings = {
  appearance: 'System',
  default_start_time: '09:30',
  pay_rate: 20,
  pay_rate_text: '20',
  default_job_shift: '',
  export_format: 'Simple',
  export_include_pay: false,
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

export function applySettings(s: Settings, sh?: string[]): void {
  settings.set({ ...s, ui_prefs: { ...DEFAULT_UI_PREFS, ...s.ui_prefs } });
  if (sh) shifts.set(sh);
}

/** Instant toggles (Lulz / Lulz sound / Reduce effects / Liquid glass / target hours), outside the Save button. */
export async function saveUiPrefs(prefs: Partial<UiPrefs>): Promise<boolean> {
  const before = get(settings);
  settings.set({ ...before, ui_prefs: { ...before.ui_prefs, ...prefs } });
  const r = await api.save_ui_prefs(prefs);
  if (r.ok && r.settings) {
    applySettings(r.settings);
    return true;
  }
  settings.set(before);
  toast(r.message ?? (r.status === 'error' ? r.error.message : 'Could not save the setting'), { tone: 'error', ms: 6000 });
  return false;
}

onEvent('dlc:status', (s) => dlc.set(s));
