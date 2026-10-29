import type { Appearance, DlcStatus, ExportFormat, Settings, SettingsDraft, VersionCheck } from '../../lib/api/types';

/** Editable Settings form state (raw text where the user types). */
export interface SettingsForm {
  appearance: Appearance;
  default_start_time: string;
  pay_rate: string;
  default_job_shift: string;
  export_format: ExportFormat;
  export_include_pay: boolean;
  target_hours: number;
}

export type FormField = 'default_start_time' | 'pay_rate' | 'default_job_shift' | 'target_hours';

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
    target_hours: s.ui_prefs.target_hours,
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

export const SHORTCUTS: { keys: string[]; what: string }[] = [
  { keys: ['F5'], what: 'Start / stop the timer' },
  { keys: ['Ctrl+N'], what: 'Add an entry' },
  { keys: ['Enter', 'F2'], what: 'Edit the selected entry' },
  { keys: ['Delete'], what: 'Delete the selected entry' },
  { keys: ['Ctrl+Z'], what: 'Undo a delete (while the note is shown)' },
  { keys: ['Click a time'], what: 'Edit Time In / Time Out in place' },
  { keys: ['Ctrl+←', 'Ctrl+→'], what: 'Previous / next month (also PageUp / PageDown)' },
  { keys: ['Ctrl+Home'], what: 'Go to the current month' },
  { keys: ['Ctrl+E'], what: 'Export to Excel' },
  { keys: ['Ctrl+I'], what: 'Import menu' },
  { keys: ['Ctrl+,'], what: 'Open Settings' },
  { keys: ['Esc', 'Ctrl+S'], what: 'In Settings: back / save' },
];
