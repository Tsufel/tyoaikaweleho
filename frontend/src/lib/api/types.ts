// Python <-> JS contract. Mirror of docs/V2_UI_API.md — change both together.

// ── Primitives ───────────────────────────────────────────────────

/** ISO date "YYYY-MM-DD". */
export type IsoDate = string;
/** Local-naive ISO datetime "YYYY-MM-DDTHH:MM:SS". */
export type IsoDateTime = string;
/** 24 h clock time "HH:MM". */
export type HHMM = string;

export type Appearance = 'System' | 'Light' | 'Dark';
export type ExportFormat = 'Simple' | 'Full';
export type Granularity = 'day' | 'week' | 'month';
export type Route = 'main' | 'stats' | 'settings';

// ── Result envelope ──────────────────────────────────────────────

export type Status =
  | 'ok'
  | 'saved'
  | 'discarded'
  | 'cancelled'
  | 'needs_confirm'
  | 'invalid'
  | 'error';

export type ErrorCode =
  | 'save_failed'
  | 'not_found'
  | 'recovery_pending'
  | 'already_running'
  | 'not_running'
  | 'stale'
  | 'file_locked'
  | 'dlc_unavailable'
  | 'dlc_failed'
  | 'network'
  | 'not_frozen'
  | 'update_failed'
  | 'ocr_failed'
  | 'internal';

export interface ApiError {
  code: ErrorCode;
  message: string;
  detail?: string;
}

interface Base {
  /** User-facing note for the status line / toast. */
  message?: string;
}

export interface OkResult extends Base {
  ok: true;
  status: 'ok' | 'saved' | 'discarded' | 'cancelled';
}
export interface NeedsConfirmResult extends Base {
  ok: false;
  status: 'needs_confirm';
  confirm: ConfirmRequest;
}
export interface InvalidResult extends Base {
  ok: false;
  status: 'invalid';
  field: string;
  message: string;
}
export interface ErrorResult extends Base {
  ok: false;
  status: 'error';
  error: ApiError;
}

/** Envelope with a success payload P. Failure variants may still carry
 *  parts of P (e.g. `timer` after a failed stop) — typed as Partial<P>. */
export type Result<P = {}> =
  | (OkResult & P)
  | (NeedsConfirmResult & Partial<P>)
  | (InvalidResult & Partial<P>)
  | (ErrorResult & Partial<P>);

// ── Confirm protocol ─────────────────────────────────────────────

export type ConfirmKind =
  | 'stop_shift'
  | 'long_shift'
  | 'over_24h'
  | 'discard_shift'
  | 'start_ahead'
  | 'long_entry'
  | 'delete_entry'
  | 'close_running'
  | 'remove_dlc';

/** Option ids per kind (choice values sent back). */
export interface ConfirmChoices {
  stop_shift: 'stop' | 'keep';
  long_shift: 'stop' | 'keep';
  over_24h: 'save' | 'discard' | 'keep';
  discard_shift: 'discard' | 'cancel';
  start_ahead: 'now' | 'earlier' | 'cancel';
  long_entry: 'save' | 'cancel';
  delete_entry: 'delete' | 'cancel';
  close_running: 'stop_close' | 'close' | 'cancel';
  remove_dlc: 'remove' | 'cancel';
}

export interface ConfirmOption {
  id: string;
  label: string;
  variant?: 'primary' | 'danger' | 'neutral';
}

export interface ConfirmDetails {
  start_iso?: IsoDateTime;
  elapsed_minutes?: number;
  capped_end?: HHMM;
  time_in?: HHMM;
  time_out?: HHMM;
  overnight?: boolean;
  description?: string;
}

export interface ConfirmRequest<K extends ConfirmKind = ConfirmKind> {
  kind: K;
  title: string;
  message: string;
  options: ConfirmOption[];
  default: ConfirmChoices[K];
  /** Answer used for Escape / closing the modal. */
  cancel: ConfirmChoices[K];
  icon: 'question' | 'warning';
  /** Echo back unchanged; a mismatch on re-call yields error/stale. */
  token?: string;
  details?: ConfirmDetails;
}

export interface ConfirmAnswer<K extends ConfirmKind = ConfirmKind> {
  kind: K;
  choice: ConfirmChoices[K];
  token?: string;
}

/** All answers so far in this flow, oldest first. */
export type ConfirmList = ConfirmAnswer[];

// ── Entries ──────────────────────────────────────────────────────

export interface WorkEntry {
  id: string;
  date: IsoDate;
  job_shift: string;
  time_in: HHMM;
  /** "" while the shift has no end. */
  time_out: HHMM | '';
}

export interface EntryRow extends WorkEntry {
  /** null when time_out is empty. */
  minutes: number | null;
  overnight: boolean;
  /** "Tue 23 Sep 2026" */
  display_date: string;
  /** "06:00 +1" for overnight, else time_out. */
  time_out_display: string;
  /** "2026-W39" (ISO year + week). */
  week_key: string;
}

/** Raw text from the add/edit modal; id absent = new entry. */
export interface EntryDraft {
  id?: string;
  date: string;
  job_shift: string;
  time_in: string;
  time_out: string;
}

export type EditableField = 'time_in' | 'time_out';

export interface WeekGroup {
  key: string;
  iso_year: number;
  week: number;
  entry_ids: string[];
  minutes: number;
  earnings: number;
}

export interface MonthData {
  year: number;
  month: number;
  /** "October 2026" */
  label: string;
  pay_rate: number;
  entries: EntryRow[];
  weeks: WeekGroup[];
  total_minutes: number;
  earnings: number;
}

// ── Timer & recovery ─────────────────────────────────────────────

export interface TimerState {
  running: boolean;
  start_iso: IsoDateTime | null;
  start_epoch_ms: number | null;
  /** Running job, or the default job while idle. */
  job_shift: string;
  default_job_shift: string;
  default_start_time: HHMM;
  pay_rate: number;
  recovery_pending: boolean;
}

export type StartMode = 'now' | 'at';
export type StopSource = 'button' | 'shortcut' | 'close';
export type RecoveryAction = 'resume' | 'save' | 'discard';

export interface Recovery {
  start_iso: IsoDateTime;
  start_epoch_ms: number;
  job_shift: string;
  elapsed_minutes: number;
  /** Elapsed >= 8 h: suggested_end is the 8-hour mark. */
  over_limit: boolean;
  suggested_end: HHMM;
}

export type TimerResult = Result<{ timer: TimerState }>;
export type StopResult = Result<{ timer: TimerState; entry?: EntryRow }>;
export type RecoveryResult = Result<{
  timer: TimerState;
  entry?: EntryRow;
  recovery: Recovery | null;
}>;

// ── Settings ─────────────────────────────────────────────────────

export interface UiPrefs {
  lulz: boolean;
  reduce_effects: boolean;
  /** Daily target for the hero ring, hours (1–24). Default 8. */
  target_hours: number;
}

export interface Settings {
  appearance: Appearance;
  default_start_time: HHMM;
  pay_rate: number;
  /** Shortest text that reads back as the same number ("20.125"). */
  pay_rate_text: string;
  default_job_shift: string;
  export_format: ExportFormat;
  export_include_pay: boolean;
  ui_prefs: UiPrefs;
}

/** Raw form values; validated by Python in one transaction. */
export interface SettingsDraft {
  appearance: Appearance;
  default_start_time: string;
  /** Accepts "20", "20,50", "20.50 €". */
  pay_rate: string;
  default_job_shift: string;
  export_format: ExportFormat;
  export_include_pay: boolean;
  ui_prefs: UiPrefs;
}

export type SettingsResult = Result<{ settings: Settings; shifts: string[] }>;

// ── Stats ────────────────────────────────────────────────────────

export interface StatsBucket {
  /** day "2026-10-29", week "2026-W44", month "2026-10" */
  key: string;
  /** day "Thu 29", week "W44", month "Oct 2026" */
  label: string;
  /** First date of the bucket (Monday for weeks). */
  start: IsoDate;
  minutes: number;
  earnings: number;
  shifts: number;
}

export interface ShiftTotal {
  job_shift: string;
  minutes: number;
  earnings: number;
  shifts: number;
}

export interface StatsData {
  start: IsoDate;
  end: IsoDate;
  granularity: Granularity;
  pay_rate: number;
  /** Every bucket in range, zero-filled, chronological. */
  buckets: StatsBucket[];
  totals: { minutes: number; earnings: number; shifts: number; worked_days: number };
  /** Sorted by minutes desc. */
  by_shift: ShiftTotal[];
  avg_per_worked_day: { minutes: number; earnings: number };
  longest: { entry: EntryRow; minutes: number } | null;
  /** Entries with no time_out — excluded from all figures. */
  open_entries: number;
}

// ── DLC / updates / changelog ────────────────────────────────────

export interface DlcStatus {
  state: 'missing' | 'ok' | 'incompatible';
  /** Installed DLC version, when loaded. */
  version: string | null;
  /** Newer published DLC version, when known. */
  update_version: string | null;
  message: string | null;
  /** Import ▸ From image (OCR) is usable. */
  ocr_available: boolean;
}

export interface VersionCheck {
  current: string | null;
  latest: string | null;
  available: boolean;
}

export type CheckUpdatesResult = Result<{ app: VersionCheck; dlc: VersionCheck | null }>;

export interface ChangelogBlock {
  version: string;
  items: string[];
}

// ── Import / export / OCR ────────────────────────────────────────

export type ExportResult = Result<{ path: string }>;

export type ImportResult = Result<{
  imported: number;
  skipped: number;
  files: number;
  errors: string[];
}>;

export interface OcrCandidate {
  date: string;
  job_shift: string;
  time_in: string;
  time_out: string;
  raw_line: string;
  confidence: 'ok' | 'uncertain';
}

/** A checked, trimmed row from the preview sheet. */
export interface OcrRow {
  date: string;
  job_shift: string;
  time_in: string;
  time_out: string;
}

export type OcrExtractResult = Result<{ candidates: OcrCandidate[]; errors: string[] }>;

export type OcrSaveResult = Result<{
  imported: number;
  skipped: number;
  /** Rows without date or time_in, skipped before saving. */
  invalid_skipped: number;
}>;

// ── Bootstrap ────────────────────────────────────────────────────

export interface Bootstrap {
  version: string;
  frozen: boolean;
  dev: boolean;
  today: IsoDate;
  now_epoch_ms: number;
  settings: Settings;
  shifts: string[];
  timer: TimerState;
  dlc: DlcStatus;
  /** Versions newer than last seen, newest first; null if none to show. */
  changelog: ChangelogBlock[] | null;
  recovery: Recovery | null;
  month: { year: number; month: number };
  error_log: string;
  data_dir: string;
  shifts_file: string;
}

// ── Api (window.pywebview.api) ───────────────────────────────────

export interface Api {
  // app / lifecycle
  bootstrap(): Promise<Result<{ data: Bootstrap }>>;
  frontend_ready(): Promise<Result>;
  set_close_guard(enabled: boolean): Promise<Result>;
  /** Results that end the app carry `quit: true` (the window is then destroyed). */
  close_app(confirm?: ConfirmList): Promise<StopResult & { quit?: true }>;
  set_theme(appearance: Appearance, dark: boolean): Promise<Result>;
  log_client_error(message: string, stack?: string): Promise<Result>;
  open_shifts_file(): Promise<Result>;

  // timer
  get_timer(): Promise<TimerResult>;
  timer_start(
    mode: StartMode,
    time?: HHMM | null,
    job_shift?: string | null,
    confirm?: ConfirmList,
  ): Promise<TimerResult>;
  timer_stop(source: StopSource, confirm?: ConfirmList): Promise<StopResult>;
  timer_discard(confirm?: ConfirmList): Promise<TimerResult>;
  recovery_resolve(
    action: RecoveryAction,
    end?: string | null,
    confirm?: ConfirmList,
  ): Promise<RecoveryResult>;

  // entries
  list_month(year: number, month: number): Promise<Result<{ data: MonthData }>>;
  get_entry(id: string): Promise<Result<{ entry: EntryRow }>>;
  save_entry(draft: EntryDraft, confirm?: ConfirmList): Promise<Result<{ entry: EntryRow }>>;
  update_entry_field(
    id: string,
    field: EditableField,
    value: string,
    confirm?: ConfirmList,
  ): Promise<Result<{ entry?: EntryRow; unchanged?: true }>>;
  delete_entry(
    id: string,
    confirm?: ConfirmList,
  ): Promise<Result<{ deleted: WorkEntry; description: string }>>;
  restore_entry(entry: WorkEntry): Promise<Result<{ entry: EntryRow }>>;

  // shifts & settings
  get_settings(): Promise<SettingsResult>;
  save_settings(draft: SettingsDraft): Promise<SettingsResult>;
  save_ui_prefs(prefs: Partial<UiPrefs>): Promise<Result<{ settings: Settings }>>;
  add_job_shift(name: string): Promise<Result<{ added: boolean; shifts: string[] }>>;

  // stats
  get_stats(
    start_iso: IsoDate,
    end_iso: IsoDate,
    granularity: Granularity,
  ): Promise<Result<{ data: StatsData }>>;

  // import / export / OCR
  export_month(year: number, month: number): Promise<ExportResult>;
  import_excel(): Promise<ImportResult>;
  ocr_pick_and_extract(): Promise<OcrExtractResult>;
  ocr_save(rows: OcrRow[]): Promise<OcrSaveResult>;

  // updates & DLC
  check_updates(): Promise<CheckUpdatesResult>;
  install_update(): Promise<Result>;
  get_dlc_status(): Promise<Result<{ dlc: DlcStatus }>>;
  dlc_install(): Promise<Result<{ verified: boolean; dlc: DlcStatus }>>;
  dlc_remove(confirm?: ConfirmList): Promise<Result<{ dlc: DlcStatus }>>;
}

export type ApiMethod = keyof Api;

// ── Events (Python -> JS) ────────────────────────────────────────

/** Dispatched as window CustomEvent 'weleho' with detail {name, payload}. */
export const EVENT_CHANNEL = 'weleho';

export interface EventMap {
  'close:requested': {};
  'app:activate': {};
  'window:visibility': { visible: boolean; focused: boolean; maximized: boolean };
  'update:available': { version: string; current: string };
  'update:installing': { version: string };
  'update:failed': { message: string };
  'dlc:update': { version: string };
  'dlc:status': DlcStatus;
  'timer:changed': TimerState;
  'data:changed': { reason: 'import' | 'ocr' | 'recovery' | 'restore' };
}

export type EventName = keyof EventMap;

export interface EventDetail<N extends EventName = EventName> {
  name: N;
  payload: EventMap[N];
}

// ── Shortcut commands (lib/shortcuts.ts) ─────────────────────────

export type CommandName =
  | 'timer.toggle'
  | 'entry.add'
  | 'entry.edit'
  | 'entry.delete'
  | 'undo'
  | 'export'
  | 'import.menu'
  | 'settings.open'
  | 'settings.save'
  | 'settings.back'
  | 'month.prev'
  | 'month.next'
  | 'month.current';
