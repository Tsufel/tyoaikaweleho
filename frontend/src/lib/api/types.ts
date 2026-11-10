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
  | 'start_backdate'
  | 'long_entry'
  | 'overlap'
  | 'delete_entry'
  | 'close_running'
  | 'remove_dlc'
  | 'restore_backup';

/** Option ids per kind (choice values sent back). */
export interface ConfirmChoices {
  stop_shift: 'stop' | 'keep';
  long_shift: 'stop' | 'keep';
  over_24h: 'save' | 'discard' | 'keep';
  discard_shift: 'discard' | 'cancel';
  start_ahead: 'now' | 'earlier' | 'cancel';
  start_backdate: 'now' | 'earlier' | 'cancel';
  long_entry: 'save' | 'cancel';
  overlap: 'save' | 'cancel';
  delete_entry: 'delete' | 'cancel';
  close_running: 'stop_close' | 'close' | 'cancel';
  remove_dlc: 'remove' | 'cancel';
  restore_backup: 'restore' | 'cancel';
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
  /** overlap: how many saved entries the shift overlaps. */
  overlaps?: number;
  /** restore_backup: the backup, its shift count, today's count (null when unreadable). */
  name?: string;
  entries?: number;
  current_entries?: number | null;
  saved_at?: IsoDateTime;
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

/**
 * `delete_entry`'s `deleted` may also carry keys a newer app version stored
 * on the entry (a break, a note): pass it back to `restore_entry` as is.
 */
export interface WorkEntry {
  id: string;
  date: IsoDate;
  job_shift: string;
  time_in: HHMM;
  /** "" while the shift has no end. */
  time_out: HHMM | '';
  /** One-line note (≤ 200 chars); stored only when not blank. */
  note?: string;
}

/** What a saved add/edit hands back so the UI can undo it: `token` is the
 *  saved entry's fingerprint, `before` the entry as it was (null = an add,
 *  undone with `delete_entry(id, [{kind:'delete_entry', choice:'delete', token}])`;
 *  else `revert_entry(before, token)`). */
export interface SaveUndo {
  token: string;
  before: WorkEntry | null;
}

export interface EntryRow extends WorkEntry {
  /** "" when the entry has none. */
  note: string;
  /** null when time_out is empty. */
  minutes: number | null;
  overnight: boolean;
  /** "Tue 23 Sep 2026" */
  display_date: string;
  /** "06:00 +1" for overnight, else time_out. */
  time_out_display: string;
  /** "2026-W39" (ISO year + week). */
  week_key: string;
  /** list_month only: overlaps another saved entry by a minute or more. */
  overlap?: boolean;
  /** list_month only: the entries it overlaps (may be in the previous month). */
  overlap_with?: OverlapRef[];
}

/** An entry an EntryRow overlaps (list_month). */
export type OverlapRef = WorkEntry;

/** Raw text from the add/edit modal; id absent = new entry. */
export interface EntryDraft {
  id?: string;
  date: string;
  job_shift: string;
  time_in: string;
  time_out: string;
  /** Absent keeps the stored note on an edit; "" clears it. */
  note?: string;
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
  /** Finnish public holidays in this month: ISO date -> name ("Vappu").
   *  Two on one date are joined with " / ". Optional for older backends. */
  holidays?: Record<IsoDate, string>;
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
/** overlap_warning: the saved shift overlaps other entries (show as a warning). */
export type StopResult = Result<{ timer: TimerState; entry?: EntryRow; overlap_warning?: string }>;
export type RecoveryResult = Result<{
  timer: TimerState;
  entry?: EntryRow;
  overlap_warning?: string;
  recovery: Recovery | null;
}>;
/** get_recovery: data_recovery is set once when a damaged data.json was
 *  replaced by a backup since bootstrap (see Bootstrap.data_recovery). */
export type GetRecoveryResult = Result<{
  timer: TimerState;
  recovery: Recovery | null;
  data_recovery: DataRecovery | null;
}>;

// ── Settings ─────────────────────────────────────────────────────

export interface UiPrefs {
  lulz: boolean;
  reduce_effects: boolean;
  /** Synthesized fire sound while Lulz is on. Default false. */
  lulz_sound: boolean;
  /** Liquid glass appearance (iOS-style refraction, specular rim). Instant toggle. */
  liquid_glass: boolean;
  /** Daily target for the hero ring, hours (1–24). Default 8. */
  target_hours: number;
  /** Timer card companion. Default 'off'. */
  pet: PetKind;
  /** Trimmed, at most 24 characters; '' = the default name. */
  pet_name: string;
  /** The Timer card's one-time pet offer was answered (or the pet set in Settings). */
  pet_hint_seen: boolean;
  /** The chosen look (views/pet/petSkins.ts); drawn once the pet's level unlocks it. */
  pet_skin: PetSkinId;
  /** In-app UI zoom, percent: 80–150 in steps of 10 (lib/zoom.ts). Default 100. */
  zoom: number;
}

export type PetKind = 'off' | 'familiar' | 'wizard';
export type PetSkinId = 'classic' | 'cosmic' | 'neon' | 'gilded' | 'legend';

export interface PetStats {
  /** Every closed shift ever, by start date (open and future ones excluded). */
  lifetime_minutes: number;
  /** Minutes per start date for the last 56 days (today included); days without a shift are left out. */
  days: Record<IsoDate, number>;
}

/** get_records (§10.3): personal records, null until a shift counts. Ties go to the earliest. */
export interface RecordsData {
  total_shifts: number;
  first_shift_date: IsoDate | null;
  /** Days from the first shift to today. */
  days_since_first: number | null;
  longest_shift: { entry: EntryRow; minutes: number } | null;
  best_day: { date: IsoDate; minutes: number } | null;
  /** key "2026-W38", start = its Monday. */
  best_week: { key: string; start: IsoDate; minutes: number } | null;
  most_shifts_week: { key: string; start: IsoDate; shifts: number } | null;
  /** key "2026-09". */
  best_month: { key: string; minutes: number } | null;
  /** time "HH:MM". */
  earliest_start: { entry: EntryRow; time: HHMM } | null;
  /** next_day: the shift ran past midnight (02:40 the next morning beats 23:00). */
  latest_finish: { entry: EntryRow; time: HHMM; next_day: boolean } | null;
  /** Workdays (Mon-Fri) at target in a row; `current` ends today, which doesn't break it before it's done. */
  streak: { current: number; best: number };
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
  /** Print the names below on the Full sheet (default off). */
  export_include_names: boolean;
  /** Printed after EMPLOYEE: / MANAGER: on the Full sheet while
   *  export_include_names is on; '' = blank line. */
  employee_name: string;
  manager_name: string;
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
  /** Left out = unchanged. */
  export_include_names?: boolean;
  /** ≤ 60 characters, no control characters; left out = unchanged. */
  employee_name?: string;
  manager_name?: string;
  ui_prefs: UiPrefs;
}

export type SettingsResult = Result<{ settings: Settings; shifts: string[] }>;

// ── Your data: backups (Settings → Your data) ────────────────────

/** Who made the copy: data.json.bak (last save), daily snapshot, Back up now,
 *  before an Excel import, before a restore, before an app update. */
export type BackupKind = 'bak' | 'daily' | 'manual' | 'pre-import' | 'pre-restore' | 'pre-update';

export interface BackupInfo {
  /** The only handle restore_backup accepts (a listed name, never a path). */
  name: string;
  kind: BackupKind;
  /** When that data was last saved (file mtime). */
  saved_at: IsoDateTime;
  size: number;
  /** false: unreadable or not app data; listed but cannot be restored. */
  ok: boolean;
  entries: number | null;
  last_entry_date: IsoDate | null;
}

export type BackupsResult = Result<{ backups: BackupInfo[]; data_dir: string; backups_dir: string }>;
export type BackupNowResult = Result<{ backup: string | null; backups: BackupInfo[] }>;
export type RestoreBackupResult = Result<{
  restored: string;
  /** pre-restore-*.json holding the data that was replaced (null when there was none). */
  safety_copy: string | null;
  settings: Settings;
  shifts: string[];
  timer: TimerState;
  backups: BackupInfo[];
}>;

/** error.log next to data.json (Settings → Your data → Error log). */
export interface ErrorLogInfo {
  exists: boolean;
  /** Bytes on disk (the log trims itself past 256 KB). */
  size: number;
  /** How many errors it holds. */
  entries: number;
  /** When the newest one was logged, or null. */
  last_at: IsoDateTime | null;
}
export type ErrorLogInfoResult = Result<ErrorLogInfo & { path: string }>;
export type SaveErrorLogResult = Result<ErrorLogInfo & { path: string }>;

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

/** Dates of the first and last stored entry (open ones included), null when there are none. */
export interface StatsSpan {
  first: IsoDate | null;
  last: IsoDate | null;
}

// ── Achievements ─────────────────────────────────────────────────

export type AchievementTier = 'bronze' | 'silver' | 'gold' | 'legendary';

export interface Achievement {
  id: string;
  title: string;
  desc: string;
  /** Medal file name in assets/medals (same as id). */
  icon: string;
  tier: AchievementTier;
  /** Shown as "???" with the hidden_<tier> medal until met. */
  hidden: boolean;
  /** cur is capped at goal; unit: shifts | h | days | weeks | € */
  progress: { cur: number; goal: number; unit: string };
  /** Date first met (or stored as seen), null while locked. */
  met_on: IsoDate | null;
}

export interface AchievementsData {
  items: Achievement[];
  /** Met but not yet acknowledged — celebrate, then ack_achievements. */
  newly: string[];
  /** Nothing acknowledged yet: show one summary toast, not one per item. */
  first_run: boolean;
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
export type ExportRangeKind = 'xlsx' | 'csv';

export type ImportResult = Result<{
  imported: number;
  skipped: number;
  files: number;
  errors: string[];
  /** Why a file gave nothing (no timesheet rows, unreadable times). */
  notes: string[];
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

export interface DataRecovery {
  /** The backup file that now stands in for data.json. */
  source: string;
  /** Where the damaged data.json was kept ('' if it couldn't be, or it was missing). */
  damaged_copy: string;
  /** Why a backup stood in: data.json didn't read, or wasn't there at all. */
  reason?: 'damaged' | 'missing';
}

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
  /** Set once when a damaged data.json was replaced by a backup. */
  data_recovery: DataRecovery | null;
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
  // get_recovery: re-offer recovery without re-running bootstrap
  get_recovery(): Promise<GetRecoveryResult>;
  // running shift: stop at a past time, fix the start or job
  timer_stop_at(end: string, confirm?: ConfirmList): Promise<StopResult>;
  timer_adjust(
    start_iso: string,
    time?: string | null,
    job_shift?: string | null,
    confirm?: ConfirmList,
  ): Promise<TimerResult>;
  recovery_resolve(
    action: RecoveryAction,
    end?: string | null,
    confirm?: ConfirmList,
  ): Promise<RecoveryResult>;

  // entries
  list_month(year: number, month: number): Promise<Result<{ data: MonthData }>>;
  get_entry(id: string): Promise<Result<{ entry: EntryRow }>>;
  save_entry(draft: EntryDraft, confirm?: ConfirmList): Promise<Result<{ entry: EntryRow } & SaveUndo>>;
  update_entry_field(
    id: string,
    field: EditableField,
    value: string,
    confirm?: ConfirmList,
  ): Promise<Result<{ entry?: EntryRow; unchanged?: true } & Partial<SaveUndo>>>;
  delete_entry(
    id: string,
    confirm?: ConfirmList,
  ): Promise<Result<{ deleted: WorkEntry; description: string }>>;
  restore_entry(entry: WorkEntry): Promise<Result<{ entry: EntryRow }>>;
  /** Undo of an edit: puts `before` back only while the entry still matches
   *  `token`; else error `stale` (or `not_found` when it is gone). */
  revert_entry(entry: WorkEntry, token: string): Promise<Result<{ entry: EntryRow; description: string }>>;

  // shifts & settings
  get_settings(): Promise<SettingsResult>;
  save_settings(draft: SettingsDraft): Promise<SettingsResult>;
  save_ui_prefs(prefs: Partial<UiPrefs>): Promise<Result<{ settings: Settings }>>;
  add_job_shift(name: string): Promise<Result<{ added: boolean; shifts: string[] }>>;

  // your data: folder, backups, restore (Settings → Your data)
  open_data_folder(): Promise<Result>;
  list_backups(): Promise<BackupsResult>;
  backup_now(): Promise<BackupNowResult>;
  /** Asks restore_backup first; on success emits data:changed {reason:'restore_backup'}. */
  restore_backup(name: string, confirm?: ConfirmList): Promise<RestoreBackupResult>;
  get_error_log_info(): Promise<ErrorLogInfoResult>;
  /** Save dialog named "Weleho error log <date>.txt": a short header (version,
   *  Windows, WebView2) and the log. `saved{path, ...info}` / `cancelled`. */
  save_error_log(): Promise<SaveErrorLogResult>;
  /** Explorer at error.log (the data folder when there is none), or at the
   *  copy save_error_log last made when `copy`. */
  reveal_error_log(copy?: boolean): Promise<Result>;

  // stats
  get_stats(
    start_iso: IsoDate,
    end_iso: IsoDate,
    granularity: Granularity,
  ): Promise<Result<{ data: StatsData }>>;
  get_stats_span(): Promise<Result<StatsSpan>>;

  // achievements
  get_achievements(): Promise<Result<AchievementsData>>;
  ack_achievements(ids: string[]): Promise<Result>;
  get_pet_stats(): Promise<Result<PetStats>>;
  // personal records (Hall of fame)
  get_records(): Promise<Result<RecordsData>>;

  // import / export / OCR
  export_month(year: number, month: number): Promise<ExportResult>;
  /** Explorer at the last exported file. */
  reveal_export(): Promise<Result>;
  import_excel(): Promise<ImportResult>;
  ocr_pick_and_extract(): Promise<OcrExtractResult>;
  ocr_save(rows: OcrRow[]): Promise<OcrSaveResult>;

  // export a date range (CSV or Simple workbook)
  /** Save dialog named "Hours 1.1.–31.12.2026.csv"; invalid(field: 'range' | 'kind'). */
  export_range(start: IsoDate, end: IsoDate, kind: ExportRangeKind): Promise<ExportResult>;

  // updates & DLC
  check_updates(): Promise<CheckUpdatesResult>;
  open_download_page(): Promise<Result>;
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
  'data:changed': { reason: 'import' | 'ocr' | 'recovery' | 'restore' | 'restore_backup' };
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
  | 'entry.duplicate'
  | 'entry.copy'
  | 'entry.filter'
  | 'undo'
  | 'export'
  | 'import.menu'
  | 'settings.open'
  | 'settings.save'
  | 'settings.back'
  | 'month.prev'
  | 'month.next'
  | 'month.current'
  // shell shortcuts: views, the cheat sheet and one secret
  | 'view.timer'
  | 'view.shifts'
  | 'view.stats'
  | 'stats.back'
  | 'help.shortcuts'
  | 'wizard.secret'
  // UI zoom (Ctrl+= / Ctrl+- / Ctrl+0) and the command palette (Ctrl+K)
  | 'zoom.in'
  | 'zoom.out'
  | 'zoom.reset'
  | 'palette.open';
