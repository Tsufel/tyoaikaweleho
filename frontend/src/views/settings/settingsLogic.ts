import type { Appearance, DlcStatus, ExportFormat, RoundMode, RoundStep, Settings, SettingsDraft, VersionCheck } from '../../lib/api/types';
import { SHORTCUT_GROUPS } from '../../lib/shortcutList';

/** Editable Settings form state (raw text where the user types). */
export interface SettingsForm {
  appearance: Appearance;
  default_start_time: string;
  pay_rate: string;
  default_job_shift: string;
  export_format: ExportFormat;
  export_include_pay: boolean;
  export_include_names: boolean;
  employee_name: string;
  manager_name: string;
  target_hours: number;
  round_enabled: boolean;
  round_mode: RoundMode;
  /** Segmented wants strings: '15' | '30' | '60'. */
  round_step: `${RoundStep}`;
}

export type FormField =
  | 'default_start_time'
  | 'pay_rate'
  | 'default_job_shift'
  | 'target_hours'
  | 'employee_name'
  | 'manager_name'
  | 'rounding';

export const TARGET_MIN = 1;
export const TARGET_MAX = 24;
export const TARGET_STEP = 0.5;

export function formFromSettings(s: Settings): SettingsForm {
  return {
    appearance: s.appearance,
    default_start_time: s.default_start_time,
    pay_rate: s.pay_rate_text || String(s.pay_rate),
    default_job_shift: s.default_job_shift,
    export_format: s.export_format,
    export_include_pay: s.export_include_pay,
    export_include_names: !!s.export_include_names,
    employee_name: s.employee_name ?? '',
    manager_name: s.manager_name ?? '',
    target_hours: s.ui_prefs.target_hours,
    round_enabled: !!s.rounding?.enabled,
    round_mode: s.rounding?.mode ?? 'nearest',
    round_step: `${s.rounding?.step ?? 30}`,
  };
}

/** What the v1.3 view compared to decide whether Back should ask. */
export function snapshot(f: SettingsForm): string {
  return JSON.stringify([
    f.default_start_time.trim(),
    f.pay_rate.trim(),
    f.default_job_shift.trim(),
    f.export_format,
    !!f.export_include_pay,
    f.appearance,
    f.target_hours,
    f.employee_name.trim(),
    f.manager_name.trim(),
    !!f.export_include_names,
    !!f.round_enabled,
    f.round_mode,
    f.round_step,
  ]);
}

export const isDirty = (initial: SettingsForm, current: SettingsForm) => snapshot(initial) !== snapshot(current);

/** Lulz / Reduce effects are saved instantly, so they come from the live settings. */
export function draftFromForm(f: SettingsForm, live: Settings): SettingsDraft {
  return {
    appearance: f.appearance,
    default_start_time: f.default_start_time.trim(),
    pay_rate: f.pay_rate.trim(),
    default_job_shift: f.default_job_shift.trim(),
    export_format: f.export_format,
    export_include_pay: !!f.export_include_pay,
    export_include_names: !!f.export_include_names,
    employee_name: f.employee_name.trim(),
    manager_name: f.manager_name.trim(),
    rounding: { enabled: !!f.round_enabled, mode: f.round_mode, step: Number(f.round_step) as RoundStep },
    ui_prefs: { ...live.ui_prefs, target_hours: f.target_hours },
  };
}

export function clampTarget(h: number): number {
  if (!Number.isFinite(h)) return 8;
  const stepped = Math.round(h / TARGET_STEP) * TARGET_STEP;
  return Math.min(TARGET_MAX, Math.max(TARGET_MIN, stepped));
}

export function formatTarget(h: number): string {
  const whole = Math.floor(h);
  const min = Math.round((h - whole) * 60);
  return min ? `${whole} h ${min} min` : `${whole} h`;
}

/** Server field name → form field (unknown fields map to null). */
export function fieldOf(name: string | undefined): FormField | null {
  switch (name) {
    case 'default_start_time':
    case 'pay_rate':
    case 'default_job_shift':
    case 'target_hours':
    case 'employee_name':
    case 'manager_name':
    case 'rounding':
      return name;
    default:
      return null;
  }
}

/** Preview of the hourly rate for the hint line, or null when unparsable. */
export function payPreview(rate: number | null, targetHours: number): string | null {
  if (rate === null) return null;
  return `€${(rate * targetHours).toFixed(2)} for a ${formatTarget(targetHours)} day`;
}

/** Rates above this get a "check the decimal point" nudge. */
export const HIGH_PAY_RATE = 200;

/** Non-blocking warning for a suspiciously high hourly rate, else null. */
export function payRateWarning(rate: number | null): string | null {
  if (rate === null || !(rate > HIGH_PAY_RATE)) return null;
  return "That's a high hourly rate. Check the decimal point.";
}

// ── Updates ──────────────────────────────────────────────────────

export type CheckState =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'uptodate'; version: string; dlcNote: string | null; at: number }
  | { kind: 'available'; version: string; current: string }
  | { kind: 'error'; message: string };

export function dlcNewerNote(dlc: VersionCheck | null | undefined): string | null {
  if (!dlc?.available || !dlc.latest) return null;
  return `A newer Image OCR DLC (v${dlc.latest}) is available — see the DLC Store below.`;
}

export function checkOutcome(
  app: VersionCheck,
  dlc: VersionCheck | null | undefined,
  installed: string,
  now = Date.now(),
): CheckState {
  if (app.available && app.latest) return { kind: 'available', version: app.latest, current: app.current ?? installed };
  return { kind: 'uptodate', version: app.current ?? installed, dlcNote: dlcNewerNote(dlc), at: now };
}

/** v1.3 manual-check text. */
export function upToDateMessage(version: string, dlcNote: string | null): string {
  return `You're up to date (v${version}).` + (dlcNote ? `\n\n${dlcNote}` : '');
}

export function updatePromptMessage(version: string, current: string): string {
  return (
    `Version ${version} is available (you have ${current}).\n\n` +
    'Download and install now?\n\n(The app will close and relaunch automatically.)'
  );
}

// ── DLC ──────────────────────────────────────────────────────────

export type DlcAction = 'install' | 'update' | 'remove';

export interface DlcView {
  tone: 'idle' | 'ok' | 'update' | 'warning';
  badge: string;
  headline: string;
  detail: string | null;
  primary: { action: 'install' | 'update'; label: string } | null;
  canRemove: boolean;
}

/** The four DLC Store states: missing, installed, installed + update, incompatible. */
export function dlcView(d: DlcStatus): DlcView {
  if (d.state === 'missing') {
    return {
      tone: 'idle',
      badge: 'Not installed',
      headline: 'Image OCR',
      detail: null,
      primary: { action: 'install', label: 'Install Image OCR' },
      canRemove: false,
    };
  }
  if (d.state === 'incompatible') {
    return {
      tone: 'warning',
      badge: d.version ? `v${d.version} · needs update` : 'Needs update',
      headline: 'Image OCR — not compatible with this app version',
      detail: d.message ?? 'Update the DLC to use Import from image again.',
      primary: {
        action: 'update',
        label: d.update_version ? `Update to v${d.update_version}` : 'Update Image OCR',
      },
      canRemove: true,
    };
  }
  if (d.update_version) {
    return {
      tone: 'update',
      badge: `v${d.version ?? '?'} → v${d.update_version}`,
      headline: 'Image OCR — installed, update available',
      detail: d.message,
      primary: { action: 'update', label: `Update to v${d.update_version}` },
      canRemove: true,
    };
  }
  return {
    tone: 'ok',
    badge: d.version ? `v${d.version}` : 'Installed',
    headline: `Image OCR — installed${d.version ? ` (v${d.version})` : ''}`,
    detail: d.message,
    primary: null,
    canRemove: true,
  };
}

export function dlcInstalledMessage(verified: boolean, d: DlcStatus): string {
  let msg: string;
  if (d.state === 'incompatible') {
    msg = `The Image OCR DLC was downloaded, but it can't be used with this app version.${d.message ? `\n\n${d.message}` : ''}`;
  } else {
    msg =
      'Image OCR DLC installed! ✅\n\n' +
      (d.ocr_available ? 'Import ▸ From image (OCR) is ready to use.\n\n' : 'Restart the app to activate Import ▸ From image.\n\n') +
      'Uses Windows built-in OCR — no extra software needed.\n' +
      'For best results with Finnish timesheets, ensure Finnish\n' +
      'is added in Windows Settings → Language.';
  }
  if (!verified) {
    msg +=
      "\n\n⚠ Note: the publisher hasn't published a checksum for this DLC version, " +
      'so the download could not be integrity-verified.';
  }
  return msg;
}

// ── Shortcuts table (v1.3 _SHORTCUTS) ────────────────────────────
// Kept in lib/shortcutList.ts so the cheat sheet and this page can't drift.

export const SHORTCUTS: { keys: string[]; what: string }[] = SHORTCUT_GROUPS.flatMap((g) => g.rows);
