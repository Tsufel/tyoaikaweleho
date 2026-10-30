// In-memory Api for `npm run dev` in a plain browser (never used inside WebView2).
// Query flags: ?mock forces it; &failsave makes every save fail (save_failed);
// &recovery=<hours> leaves an unfinished shift; &running=<hours> starts with a
// running shift; &changelog shows the changelog; &update emits update:available;
// &empty starts with no shifts; &dlc installs the OCR DLC; &lulz turns Lulz on;
// &sound turns Lulz sound on; &glass turns Liquid glass on; &glassdebug (DEV only)
// replaces every liquid-glass lens map with a hard left/right split.
// &achnew skips the achievements first-run summary so each unlock animates.
// &pet=familiar|wizard turns the Timer card pet on.
// &certfail makes update checks and installs fail as on a PC missing GitHub's root.
// window.__welehoMock exposes the same switches at runtime.

import { emitEvent } from './events';
import type {
  Api,
  Appearance,
  ConfirmAnswer,
  ConfirmKind,
  ConfirmList,
  ConfirmOption,
  ConfirmRequest,
  DlcStatus,
  EntryRow,
  EventMap,
  EventName,
  Granularity,
  MonthData,
  OcrRow,
  Recovery,
  Settings,
  SettingsDraft,
  StatsBucket,
  TimerState,
  UiPrefs,
  WorkEntry,
} from './types';
import {
  LONG_SHIFT_MINUTES,
  MIN_SHIFT_SECONDS,
  describeEntry,
  entryMinutes,
  formatDuration,
  fromIsoDate,
  hhmm,
  isOvernight,
  isoWeek,
  monthLabel,
  MONTHS_SHORT,
  parseDateInput,
  parsePayRate,
  parseTimeInput,
  resolveStartTime,
  startTimeNeedsConfirm,
  strftime,
  toIsoDate,
  toIsoDateTime,
  weekKey,
} from '../time';
import { ACHIEVEMENT_IDS, evaluateAchievements, petStats, withSeen } from './mockAchievements';

const VERSION = '2.0.1';
const CERT_FAIL =
  "GitHub's security certificate could not be verified, so the connection was stopped.\n\n" +
  'Antivirus HTTPS scanning, a network proxy or a wrong date and time on this PC can cause this.';
const DEFAULT_SHIFTS = ['Sales', 'Support', 'Warehouse', 'Sales/Support', 'Training', 'Onboarding'];
const HOUR = 3_600_000;

interface Session {
  start: Date;
  job: string;
}

export interface MockControls {
  failSave: boolean;
  /** Leave an unfinished shift started `hoursAgo` (shown on next bootstrap). */
  setRecovery(hoursAgo: number | null): void;
  /** Start a running shift `hoursAgo` (e.g. 25 → over_24h flow). */
  setRunning(hoursAgo: number | null): void;
  emit<N extends EventName>(name: N, payload: EventMap[N]): void;
  entries(): WorkEntry[];
}

declare global {
  interface Window {
    __welehoMock?: MockControls;
  }
}

// ── helpers ──────────────────────────────────────────────────────

const pad2 = (n: number) => String(n).padStart(2, '0');
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const latency = () => wait(40 + Math.random() * 120);

function rng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function answerFor<K extends ConfirmKind>(list: ConfirmList | undefined, kind: K): ConfirmAnswer<K> | undefined {
  const all = (list ?? []).filter((a) => a.kind === kind);
  return all[all.length - 1] as ConfirmAnswer<K> | undefined;
}

function needs<K extends ConfirmKind>(req: ConfirmRequest<K>): any {
  return { ok: false, status: 'needs_confirm', confirm: req };
}
const okR = (status: 'ok' | 'saved' | 'discarded' | 'cancelled', payload: object = {}, message?: string): any => ({
  ok: true,
  status,
  ...(message ? { message } : {}),
  ...payload,
});
const err = (code: string, message: string, payload: object = {}): any => ({
  ok: false,
  status: 'error',
  message,
  error: { code, message },
  ...payload,
});
const invalid = (field: string, message: string, payload: object = {}): any => ({
  ok: false,
  status: 'invalid',
  field,
  message,
  ...payload,
});

function toRow(e: WorkEntry): EntryRow {
  const d = fromIsoDate(e.date) ?? new Date();
  const has = !!e.time_out;
  const overnight = has && isOvernight(e.time_in, e.time_out);
  return {
    ...e,
    minutes: has ? entryMinutes(e.time_in, e.time_out) : null,
    overnight,
    display_date: strftime(d, '%a %d %b %Y'),
    time_out_display: overnight ? `${e.time_out} +1` : e.time_out,
    week_key: weekKey(d),
  };
}

const sortEntries = (a: WorkEntry, b: WorkEntry) =>
  a.date === b.date ? a.time_in.localeCompare(b.time_in) : a.date.localeCompare(b.date);

function seedEntries(today: Date): WorkEntry[] {
  const rand = rng(20260929);
  const out: WorkEntry[] = [];
  const first = new Date(today.getFullYear(), today.getMonth() - 2, 1);
  let n = 0;
  for (let d = new Date(first); d < today; d.setDate(d.getDate() + 1)) {
    const wd = (d.getDay() + 6) % 7;
    const workday = wd < 5 ? rand() < 0.8 : rand() < 0.12;
    if (!workday) continue;
    const startSlot = 14 + Math.floor(rand() * 6); // 07:00–09:30
    const startMin = startSlot * 30 + (rand() < 0.3 ? 15 : 0);
    let len = 300 + Math.floor(rand() * 9) * 30; // 5h–9h
    if (rand() < 0.04) len = 15 * 60; // the odd very long shift
    const evening = rand() < 0.06;
    const s = evening ? 18 * 60 + Math.floor(rand() * 4) * 30 : startMin;
    const e = (s + len) % (24 * 60);
    const time_in = `${pad2(Math.floor(s / 60))}:${pad2(s % 60)}`;
    const time_out = `${pad2(Math.floor(e / 60))}:${pad2(e % 60)}`;
    out.push({
      id: `m${++n}`,
      date: toIsoDate(d),
      job_shift: DEFAULT_SHIFTS[Math.floor(rand() * rand() * DEFAULT_SHIFTS.length)],
      time_in,
      time_out,
    });
  }
  // one shift with no end (excluded from totals)
  if (out.length > 3) out[out.length - 3] = { ...out[out.length - 3], time_out: '' };
  return out;
}

// ── factory ──────────────────────────────────────────────────────

export function createMockApi(): Api {
  const q = new URLSearchParams(typeof location !== 'undefined' ? location.search : '');
  const today = new Date();
  let entries: WorkEntry[] = q.has('empty') ? [] : seedEntries(today);
  let nextId = entries.length + 1;
  let shifts = [...DEFAULT_SHIFTS];
  let settings: Settings = {
    appearance: 'System',
    default_start_time: '09:30',
    pay_rate: 20,
    pay_rate_text: '20',
    default_job_shift: 'Sales',
    export_format: 'Simple',
    export_include_pay: false,
    ui_prefs: {
      lulz: q.has('lulz'),
      reduce_effects: false,
      lulz_sound: q.has('sound'),
      liquid_glass: q.has('glass'),
      target_hours: 8,
      pet: q.get('pet') === 'wizard' ? 'wizard' : q.get('pet') === 'familiar' ? 'familiar' : 'off',
      pet_name: '',
    },
  };
  let dlc: DlcStatus = q.has('dlc')
    ? { state: 'ok', version: '1.0.2', update_version: null, message: null, ocr_available: true }
    : { state: 'missing', version: null, update_version: null, message: null, ocr_available: false };
  let session: Session | null = null;
  // null = first run (one summary toast); &achnew starts with nothing acknowledged
  // but past first run, so every met achievement gets its own unlock.
  let achievementsSeen: Record<string, string> | null = q.has('achnew') ? {} : null;
  let recoverySession: Session | null = null;
  let closeGuard = false;
  let changelogShown = !q.has('changelog');

  const hoursParam = (k: string) => {
    const v = q.get(k);
    if (v === null) return null;
    const h = Number(v || '3');
    return Number.isFinite(h) ? h : 3;
  };
  const r0 = hoursParam('recovery');
  if (r0 !== null) recoverySession = { start: new Date(Date.now() - r0 * HOUR), job: 'Support' };
  const run0 = hoursParam('running');
  if (run0 !== null) session = { start: new Date(Date.now() - run0 * HOUR), job: 'Sales' };

  const controls: MockControls = {
    failSave: q.has('failsave'),
    setRecovery(h) {
      recoverySession = h === null ? null : { start: new Date(Date.now() - h * HOUR), job: 'Support' };
    },
    setRunning(h) {
      session = h === null ? null : { start: new Date(Date.now() - h * HOUR), job: settings.default_job_shift || 'Sales' };
      emitEvent('timer:changed', timerState());
    },
    emit: (name, payload) => emitEvent(name, payload),
    entries: () => entries.map((e) => ({ ...e })),
  };
  if (typeof window !== 'undefined') window.__welehoMock = controls;

  if (q.has('update')) {
    setTimeout(() => emitEvent('update:available', { version: '2.1.0', current: VERSION }), 2500);
  }

  function timerState(): TimerState {
    return {
      running: !!session,
      start_iso: session ? toIsoDateTime(session.start) : null,
      start_epoch_ms: session ? session.start.getTime() : null,
      job_shift: session ? session.job : settings.default_job_shift,
      default_job_shift: settings.default_job_shift,
      default_start_time: settings.default_start_time,
      pay_rate: settings.pay_rate,
      recovery_pending: !!recoverySession,
    };
  }

  function recovery(endOverride?: string): Recovery | null {
    if (!recoverySession) return null;
    const { start, job } = recoverySession;
    const elapsed = Math.max(0, Math.floor((Date.now() - start.getTime()) / 60000));
    const over = elapsed >= 8 * 60;
    return {
      start_iso: toIsoDateTime(start),
      start_epoch_ms: start.getTime(),
      job_shift: job,
      elapsed_minutes: elapsed,
      over_limit: over,
      suggested_end: endOverride ?? (over ? hhmm(new Date(start.getTime() + 8 * HOUR)) : hhmm(new Date())),
    };
  }

  /** storage.save_entry: fails when failSave is on. */
  function persist(e: WorkEntry): EntryRow | null {
    if (controls.failSave) return null;
    const i = entries.findIndex((x) => x.id === e.id);
    if (i >= 0) entries[i] = e;
    else entries.push(e);
    entries.sort(sortEntries);
    return toRow(e);
  }
  const saveFailMsg = (what = 'data.json') =>
    `[Errno 13] Permission denied: '${what}' (mock: save failures are switched on)`;

  function month(year: number, m: number): MonthData {
    const prefix = `${year}-${pad2(m)}-`;
    const rows = entries.filter((e) => e.date.startsWith(prefix)).sort(sortEntries).map(toRow);
    const weeks = new Map<string, { iso_year: number; week: number; ids: string[]; minutes: number }>();
    for (const r of rows) {
      const [iy, w] = isoWeek(fromIsoDate(r.date)!);
      const g = weeks.get(r.week_key) ?? { iso_year: iy, week: w, ids: [], minutes: 0 };
      g.ids.push(r.id);
      g.minutes += r.minutes ?? 0;
      weeks.set(r.week_key, g);
    }
    const total = rows.reduce((s, r) => s + (r.minutes ?? 0), 0);
    const pay = (min: number) => Math.round((min / 60) * settings.pay_rate * 100) / 100;
    return {
      year,
      month: m,
      label: monthLabel(year, m),
      pay_rate: settings.pay_rate,
      entries: rows,
      weeks: [...weeks.entries()]
        .sort((a, b) => a[1].iso_year - b[1].iso_year || a[1].week - b[1].week)
        .map(([key, g]) => ({ key, iso_year: g.iso_year, week: g.week, entry_ids: g.ids, minutes: g.minutes, earnings: pay(g.minutes) })),
      total_minutes: total,
      earnings: pay(total),
    };
  }

  const elapsedMin = (s: Session) => Math.floor((Date.now() - s.start.getTime()) / 60000);
  const agoText = (s: Session) => formatDuration(elapsedMin(s));

  function discardConfirm(token?: string): ConfirmRequest<'discard_shift'> {
    return {
      kind: 'discard_shift',
      title: 'Discard shift?',
      message: 'Discard this shift? It will not be saved.',
      options: [
        { id: 'discard', label: 'Discard', variant: 'danger' },
        { id: 'cancel', label: 'Cancel', variant: 'neutral' },
      ],
      default: 'cancel',
      cancel: 'cancel',
      icon: 'warning',
      token,
    };
  }

  /** §6.1 — shared by timer_stop and close_app(stop_close). */
  function stopFlow(source: 'button' | 'shortcut' | 'close', confirm: ConfirmList | undefined): any {
    if (!session) return okR('ok', { timer: timerState() });
    const s = session;
    const token = toIsoDateTime(s.start);
    const stale = (confirm ?? []).some((a) => a.token !== undefined && a.token !== token);
    if (stale) return err('stale', 'The shift changed in the meantime.', { timer: timerState() });
    const elapsedSec = (Date.now() - s.start.getTime()) / 1000;
    const minutes = Math.floor(elapsedSec / 60);
    const long = minutes > LONG_SHIFT_MINUTES;

    let skipLong = source === 'close';
    if (source === 'shortcut') {
      const a = answerFor(confirm, 'stop_shift');
      if (!a) {
        return needs<'stop_shift'>({
          kind: 'stop_shift',
          title: 'Stop shift?',
          message: `Stop the shift started at ${hhmm(s.start)} (${agoText(s)} ago) and save it?`,
          options: [
            { id: 'stop', label: 'Yes', variant: 'primary' },
            { id: 'keep', label: 'No', variant: 'neutral' },
          ],
          default: 'stop',
          cancel: 'keep',
          icon: long ? 'warning' : 'question',
          token,
          details: { start_iso: token, elapsed_minutes: minutes },
        });
      }
      if (a.choice === 'keep') return okR('cancelled', { timer: timerState() });
      skipLong = true;
    }

    if (elapsedSec < MIN_SHIFT_SECONDS) {
      session = null;
      return okR('discarded', { timer: timerState() }, 'Shift under a minute — not saved');
    }

    let timeOut = hhmm(new Date());
    if (minutes >= 24 * 60) {
      const capped = hhmm(new Date(s.start.getTime() + 8 * HOUR));
      const a = answerFor(confirm, 'over_24h');
      if (!a) {
        return needs<'over_24h'>({
          kind: 'over_24h',
          title: 'Shift over 24 hours',
          message:
            `This shift has been running for ${agoText(s)} (since ${strftime(s.start, '%a %d %b %H:%M')}), ` +
            `longer than one entry can hold.\n\nSave it ending at the 8-hour mark (${capped}) and fix the end ` +
            'time in the table, or discard it?',
          options: [
            { id: 'save', label: `Save until ${capped}`, variant: 'primary' },
            { id: 'discard', label: 'Discard', variant: 'danger' },
            { id: 'keep', label: 'Keep running', variant: 'neutral' },
          ],
          default: 'keep',
          cancel: 'keep',
          icon: 'warning',
          token,
          details: { start_iso: token, elapsed_minutes: minutes, capped_end: capped },
        });
      }
      if (a.choice === 'keep') return okR('cancelled', { timer: timerState() });
      if (a.choice === 'discard') {
        const d = answerFor(confirm, 'discard_shift');
        if (!d) return needs(discardConfirm(token));
        if (d.choice !== 'discard') return okR('cancelled', { timer: timerState() });
        session = null;
        return okR('discarded', { timer: timerState() }, 'Shift discarded');
      }
      timeOut = capped;
    } else if (!skipLong && source === 'button' && long) {
      const a = answerFor(confirm, 'long_shift');
      if (!a) {
        return needs<'long_shift'>({
          kind: 'long_shift',
          title: 'Long shift',
          message:
            `This shift has been running for ${agoText(s)} (since ${strftime(s.start, '%a %d %b %H:%M')}).` +
            '\n\nStop and save it?\n\nNo keeps the timer running.',
          options: [
            { id: 'stop', label: 'Yes', variant: 'primary' },
            { id: 'keep', label: 'No', variant: 'neutral' },
          ],
          default: 'stop',
          cancel: 'keep',
          icon: 'warning',
          token,
          details: { start_iso: token, elapsed_minutes: minutes },
        });
      }
      if (a.choice === 'keep') return okR('cancelled', { timer: timerState() });
    }

    // stop → save; on failure the same shift keeps running (§4.3)
    session = null;
    const entry: WorkEntry = {
      id: `m${++nextId}`,
      date: toIsoDate(s.start),
      job_shift: s.job,
      time_in: hhmm(s.start),
      time_out: timeOut,
    };
    const row = persist(entry);
    if (!row) {
      session = s;
      return err(
        'save_failed',
        `The shift could not be saved and is still running.\n\n${saveFailMsg()}\n\n` +
          'Close any program that may be locking data.json and press STOP again.',
        { timer: timerState() },
      );
    }
    return okR('saved', { timer: timerState(), entry: row });
  }

  function longEntryConfirm(tIn: string, tOut: string): ConfirmRequest<'long_entry'> {
    const minutes = entryMinutes(tIn, tOut);
    const next = isOvernight(tIn, tOut) ? ' (ending the next day)' : '';
    return {
      kind: 'long_entry',
      title: 'Unusually long shift',
      message: `${tIn}–${tOut} is ${formatDuration(minutes)}${next}. Save it anyway?`,
      options: [
        { id: 'save', label: 'Save anyway', variant: 'primary' },
        { id: 'cancel', label: 'Cancel', variant: 'neutral' },
      ],
      default: 'save',
      cancel: 'cancel',
      icon: 'warning',
      details: { time_in: tIn, time_out: tOut, overnight: isOvernight(tIn, tOut) },
    };
  }

  function statsBuckets(start: Date, end: Date, g: Granularity): StatsBucket[] {
    const out = new Map<string, StatsBucket>();
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      let key: string, label: string, bStart: Date;
      if (g === 'day') {
        key = toIsoDate(d);
        label = strftime(d, '%a %d').replace(/ 0(\d)$/, ' $1');
        bStart = d;
      } else if (g === 'week') {
        key = weekKey(d);
        label = `W${isoWeek(d)[1]}`;
        bStart = new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7));
      } else {
        key = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}`;
        label = `${MONTHS_SHORT[d.getMonth()]} ${d.getFullYear()}`;
        bStart = new Date(d.getFullYear(), d.getMonth(), 1);
      }
      if (!out.has(key)) out.set(key, { key, label, start: toIsoDate(bStart), minutes: 0, earnings: 0, shifts: 0 });
    }
    return [...out.values()];
  }

  const api: Api = {
    // ── app / lifecycle ──
    async bootstrap() {
      await latency();
      const changelog = changelogShown
        ? null
        : [
            { version: '2.0.0', items: ['A brand new look: glass, colour and motion.', 'Stats view with charts.', 'Light, dark and System themes.'] },
            { version: '1.3.0', items: ['Dark mode, shortcuts and undo.', 'No more lost data on save errors.'] },
          ];
      changelogShown = true;
      return okR('ok', {
        data: {
          version: VERSION,
          frozen: false,
          dev: true,
          today: toIsoDate(new Date()),
          now_epoch_ms: Date.now(),
          settings: structuredClone(settings),
          shifts: [...shifts],
          timer: timerState(),
          dlc: { ...dlc },
          changelog,
          recovery: recovery(),
          month: { year: new Date().getFullYear(), month: new Date().getMonth() + 1 },
          error_log: 'C:\\Users\\you\\AppData\\Roaming\\Tyoaikaweleho\\error.log (mock)',
          data_dir: 'C:\\Users\\you\\AppData\\Roaming\\Tyoaikaweleho (mock)',
          shifts_file: 'shifts.txt (mock)',
        },
      });
    },
    async frontend_ready() {
      return okR('ok');
    },
    async set_close_guard(enabled) {
      closeGuard = enabled;
      return okR('ok');
    },
    async close_app(confirm) {
      await latency();
      if (!session) {
        console.info('[mock] window would close now (close guard %s)', closeGuard ? 'on' : 'off');
        return okR('ok', { timer: timerState() });
      }
      const a = answerFor(confirm, 'close_running');
      if (!a) {
        return needs<'close_running'>({
          kind: 'close_running',
          title: 'A shift is running',
          message:
            `A shift is running (started ${hhmm(session.start)}, ${agoText(session)} ago).\n\n` +
            'Stop and save it before closing? If you close anyway, it will be offered for recovery next time.',
          options: [
            { id: 'stop_close', label: 'Stop, save & close', variant: 'primary' },
            { id: 'close', label: 'Close anyway', variant: 'neutral' },
            { id: 'cancel', label: 'Stay open', variant: 'neutral' },
          ],
          default: 'stop_close',
          cancel: 'cancel',
          icon: 'warning',
          token: toIsoDateTime(session.start),
          details: { start_iso: toIsoDateTime(session.start), elapsed_minutes: elapsedMin(session) },
        });
      }
      if (a.choice === 'cancel') return okR('cancelled', { timer: timerState() });
      if (a.choice === 'close') {
        // session kept → recovery on next launch (§4.4)
        recoverySession = session;
        session = null;
        console.info('[mock] closed anyway; the shift will be offered for recovery on reload');
        return okR('ok', { timer: timerState() });
      }
      const r = stopFlow('close', confirm);
      if (r.status === 'saved' || r.status === 'discarded') console.info('[mock] window would close now');
      return r;
    },
    async set_theme(_appearance: Appearance, _dark: boolean) {
      return okR('ok');
    },
    async log_client_error(message, stack) {
      console.warn('[mock] client error logged:', message, stack ?? '');
      return okR('ok');
    },
    async open_shifts_file() {
      console.info('[mock] would open shifts.txt');
      return okR('ok');
    },

    // ── timer ──
    async get_timer() {
      return okR('ok', { timer: timerState() });
    },
    async timer_start(mode, time, job_shift, confirm) {
      await latency();
      if (session) return err('already_running', 'A shift is already running.', { timer: timerState() });
      if (recoverySession) {
        return err('recovery_pending', 'Resolve the unfinished shift first.', { timer: timerState() });
      }
      const job = (job_shift ?? '').trim() || settings.default_job_shift || '—';
      if (mode === 'now') {
        session = { start: new Date(), job };
        return okR('ok', { timer: timerState() });
      }
      const t = parseTimeInput(time ?? '');
      if (!t) return invalid('time', 'Start time must be a valid time (e.g. 09:30).', { timer: timerState() });
      const [h, m] = t.split(':').map(Number);
      const now = new Date();
      if (startTimeNeedsConfirm(h, m, now)) {
        const a = answerFor(confirm, 'start_ahead');
        if (!a) {
          const resolved = resolveStartTime(h, m, now);
          const which = toIsoDate(resolved) === toIsoDate(now) ? 'today' : 'yesterday';
          return needs<'start_ahead'>({
            kind: 'start_ahead',
            title: "Start time hasn't come yet",
            message:
              `It's ${hhmm(now)} now, so the next ${t} is still ahead.\n\n` +
              `Start the shift now, or from ${t} ${which} (${strftime(resolved, '%a %d %b')})?`,
            options: [
              { id: 'now', label: `Start now (${hhmm(now)})`, variant: 'primary' },
              { id: 'earlier', label: `From ${which} ${t}`, variant: 'neutral' },
              { id: 'cancel', label: 'Cancel', variant: 'neutral' },
            ],
            default: 'now',
            cancel: 'cancel',
            icon: 'question',
          });
        }
        if (a.choice === 'cancel') return okR('cancelled', { timer: timerState() });
        if (a.choice === 'now') {
          session = { start: new Date(), job };
          return okR('ok', { timer: timerState() });
        }
      }
      session = { start: resolveStartTime(h, m, new Date()), job };
      return okR('ok', { timer: timerState() });
    },
    async timer_stop(source, confirm) {
      await latency();
      return stopFlow(source, confirm);
    },
    async timer_discard(confirm) {
      await latency();
      if (!session) return okR('ok', { timer: timerState() });
      const token = toIsoDateTime(session.start);
      const a = answerFor(confirm, 'discard_shift');
      if (!a) return needs(discardConfirm(token));
      if (a.token !== undefined && a.token !== token) return err('stale', 'The shift changed in the meantime.', { timer: timerState() });
      if (a.choice !== 'discard') return okR('cancelled', { timer: timerState() });
      session = null;
      return okR('discarded', { timer: timerState() }, 'Shift discarded');
    },
    async recovery_resolve(action, end, confirm) {
      await latency();
      const rec = recovery();
      if (!rec || !recoverySession) return okR('ok', { timer: timerState(), recovery: null });
      const rs = recoverySession;
      if (action === 'resume') {
        session = rs;
        recoverySession = null;
        return okR('ok', { timer: timerState(), recovery: null });
      }
      if (action === 'discard') {
        const a = answerFor(confirm, 'discard_shift');
        if (!a) return needs(discardConfirm(rec.start_iso));
        if (a.choice !== 'discard') return okR('cancelled', { timer: timerState(), recovery: rec });
        recoverySession = null;
        return okR('discarded', { timer: timerState(), recovery: null }, 'Shift discarded');
      }
      const t = parseTimeInput(end ?? '');
      if (!t) return invalid('end', 'End time must be a valid time (e.g. 17:00).', { timer: timerState(), recovery: rec });
      const row = persist({ id: `m${++nextId}`, date: toIsoDate(rs.start), job_shift: rs.job, time_in: hhmm(rs.start), time_out: t });
      if (!row) {
        // recovery stays pending (§4.5)
        return err('save_failed', `The shift could not be saved.\n\n${saveFailMsg()}`, {
          timer: timerState(),
          recovery: recovery(t),
        });
      }
      recoverySession = null;
      return okR('saved', { timer: timerState(), entry: row, recovery: null });
    },

    // ── entries ──
    async list_month(year, m) {
      await latency();
      return okR('ok', { data: month(year, m) });
    },
    async get_entry(id) {
      const e = entries.find((x) => x.id === id);
      return e ? okR('ok', { entry: toRow(e) }) : err('not_found', 'That shift no longer exists.');
    },
    async save_entry(draft, confirm) {
      await latency();
      const date = parseDateInput(draft.date);
      if (!date) return invalid('date', 'Enter the date as YYYY-MM-DD or D.M.YYYY (e.g. 2026-09-23 or 23.9.2026).');
      const tIn = parseTimeInput(draft.time_in);
      if (!tIn) return invalid('time_in', 'Time In must be a valid time (e.g. 09:30).');
      const outRaw = draft.time_out.trim();
      const tOut = outRaw ? parseTimeInput(outRaw) : '';
      if (tOut === null) return invalid('time_out', 'Time Out must be a valid time (e.g. 17:00).');
      if (draft.id && !entries.some((e) => e.id === draft.id)) return err('not_found', 'That shift no longer exists.');
      if (tOut && entryMinutes(tIn, tOut) > LONG_SHIFT_MINUTES) {
        const a = answerFor(confirm, 'long_entry');
        if (!a) return needs(longEntryConfirm(tIn, tOut));
        if (a.choice !== 'save') return okR('cancelled');
      }
      const e: WorkEntry = {
        id: draft.id ?? `m${++nextId}`,
        date,
        job_shift: draft.job_shift.trim(),
        time_in: tIn,
        time_out: tOut,
      };
      const row = persist(e);
      if (!row) return err('save_failed', `The shift could not be saved.\n\n${saveFailMsg()}`);
      return okR('saved', { entry: row });
    },
    async update_entry_field(id, field, value, confirm) {
      await latency();
      const e = entries.find((x) => x.id === id);
      if (!e) return err('not_found', 'That shift no longer exists.');
      const raw = value.replace(/\s*\+1\s*$/, '').trim();
      const parsed = parseTimeInput(raw);
      if (parsed === null) {
        if (raw === e[field]) return okR('ok', { unchanged: true });
        return invalid(field, field === 'time_in' ? 'Time In must be a valid time (e.g. 09:30).' : 'Time Out must be a valid time (e.g. 17:00).');
      }
      if (parsed === e[field]) return okR('ok', { unchanged: true });
      const next = { ...e, [field]: parsed };
      if (next.time_out && entryMinutes(next.time_in, next.time_out) > LONG_SHIFT_MINUTES) {
        const a = answerFor(confirm, 'long_entry');
        if (!a) return needs(longEntryConfirm(next.time_in, next.time_out));
        if (a.choice !== 'save') return okR('cancelled');
      }
      const row = persist(next);
      if (!row) return err('save_failed', `The change could not be saved.\n\n${saveFailMsg()}`);
      return okR('saved', { entry: row });
    },
    async delete_entry(id, confirm) {
      await latency();
      const e = entries.find((x) => x.id === id);
      if (!e) return err('not_found', 'That shift no longer exists.');
      const description = describeEntry(e);
      const a = answerFor(confirm, 'delete_entry');
      if (!a) {
        return needs<'delete_entry'>({
          kind: 'delete_entry',
          title: 'Delete shift?',
          message: `Delete the shift ${description}?`,
          options: [
            { id: 'delete', label: 'Delete', variant: 'danger' },
            { id: 'cancel', label: 'Cancel', variant: 'neutral' },
          ],
          default: 'cancel',
          cancel: 'cancel',
          icon: 'warning',
          token: id,
          details: { time_in: e.time_in, time_out: e.time_out, description },
        });
      }
      if (a.choice !== 'delete') return okR('cancelled');
      if (controls.failSave) return err('save_failed', `The shift could not be deleted.\n\n${saveFailMsg()}`);
      entries = entries.filter((x) => x.id !== id);
      return okR('ok', { deleted: { ...e }, description });
    },
    async restore_entry(entry) {
      await latency();
      const row = persist({ ...entry });
      if (!row) return err('save_failed', `Could not restore ${describeEntry(entry)}.`);
      return okR('saved', { entry: row });
    },

    // ── shifts & settings ──
    async get_settings() {
      return okR('ok', { settings: structuredClone(settings), shifts: [...shifts] });
    },
    async save_settings(draft: SettingsDraft) {
      await latency();
      const start = parseTimeInput(draft.default_start_time);
      if (!start) return invalid('default_start_time', 'Default start time must be a valid time (e.g. 09:30).');
      const rate = parsePayRate(draft.pay_rate);
      if (rate === null) return invalid('pay_rate', 'Pay rate must be a positive number (e.g. 20 or 20,50).');
      const th = draft.ui_prefs.target_hours;
      if (!(th >= 1 && th <= 24)) return invalid('target_hours', 'Daily target must be between 1 and 24 hours.');
      if (controls.failSave) return err('save_failed', `Settings could not be written: ${saveFailMsg()}`);
      const job = draft.default_job_shift.trim();
      if (job && !shifts.some((s) => s.toLowerCase() === job.toLowerCase())) shifts = [...shifts, job];
      settings = {
        appearance: draft.appearance,
        default_start_time: start,
        pay_rate: rate,
        pay_rate_text: String(rate),
        default_job_shift: job,
        export_format: draft.export_format,
        export_include_pay: draft.export_include_pay,
        ui_prefs: { ...draft.ui_prefs },
      };
      emitEvent('timer:changed', timerState());
      return okR('saved', { settings: structuredClone(settings), shifts: [...shifts] });
    },
    async save_ui_prefs(prefs: Partial<UiPrefs>) {
      if (controls.failSave) return err('save_failed', `Settings could not be written: ${saveFailMsg()}`);
      if (prefs.pet !== undefined && !['off', 'familiar', 'wizard'].includes(prefs.pet)) {
        return invalid('ui_prefs', 'pet must be off, familiar or wizard');
      }
      if (prefs.pet_name !== undefined) {
        const name = typeof prefs.pet_name === 'string' ? prefs.pet_name.trim().replace(/\s+/g, ' ') : null;
        // like storage._pet_name_error: control characters first, then length in code points
        if (name !== null && /[\p{Cc}\p{Cs}\p{Co}\p{Zl}\p{Zp}‪-‮⁦-⁩]/u.test(prefs.pet_name as string)) {
          return invalid('pet_name', "Pet names can't contain control characters.");
        }
        if (name === null || [...name].length > 24) return invalid('pet_name', 'Give your pet a name of at most 24 characters.');
        prefs = { ...prefs, pet_name: name };
      }
      settings = { ...settings, ui_prefs: { ...settings.ui_prefs, ...prefs } };
      return okR('saved', { settings: structuredClone(settings) });
    },
    async add_job_shift(name) {
      const n = name.trim();
      if (!n) return invalid('name', 'Enter a shift name.');
      if (shifts.some((s) => s.toLowerCase() === n.toLowerCase())) {
        return okR('ok', { added: false, shifts: [...shifts] }, `'${n}' is already in the shift list.`);
      }
      shifts = [...shifts, n];
      return okR('saved', { added: true, shifts: [...shifts] });
    },

    // ── stats ──
    async get_stats(startIso, endIso, granularity) {
      await latency();
      const start = fromIsoDate(startIso);
      const end = fromIsoDate(endIso);
      if (!start || !end || end < start || (end.getTime() - start.getTime()) / 86_400_000 > 3700) {
        return invalid('range', 'Pick an end date on or after the start date.');
      }
      const buckets = statsBuckets(start, end, granularity);
      const byKey = new Map(buckets.map((b) => [b.key, b]));
      const rate = settings.pay_rate;
      const pay = (min: number) => Math.round((min / 60) * rate * 100) / 100;
      const byShift = new Map<string, { minutes: number; shifts: number }>();
      const days = new Set<string>();
      let open = 0;
      let longest: { entry: EntryRow; minutes: number } | null = null;
      let totalMin = 0;
      let totalShifts = 0;
      for (const e of entries) {
        if (e.date < startIso || e.date > endIso) continue;
        if (!e.time_out) {
          open++;
          continue;
        }
        const d = fromIsoDate(e.date)!;
        const min = entryMinutes(e.time_in, e.time_out);
        const key =
          granularity === 'day' ? e.date : granularity === 'week' ? weekKey(d) : e.date.slice(0, 7);
        const b = byKey.get(key);
        if (b) {
          b.minutes += min;
          b.shifts += 1;
        }
        const s = byShift.get(e.job_shift) ?? { minutes: 0, shifts: 0 };
        s.minutes += min;
        s.shifts += 1;
        byShift.set(e.job_shift, s);
        if (min > 0) days.add(e.date);
        totalMin += min;
        totalShifts += 1;
        if (!longest || min > longest.minutes) longest = { entry: toRow(e), minutes: min };
      }
      for (const b of buckets) b.earnings = pay(b.minutes);
      const worked = days.size;
      return okR('ok', {
        data: {
          start: startIso,
          end: endIso,
          granularity,
          pay_rate: rate,
          buckets,
          totals: { minutes: totalMin, earnings: pay(totalMin), shifts: totalShifts, worked_days: worked },
          by_shift: [...byShift.entries()]
            .map(([job_shift, s]) => ({ job_shift, minutes: s.minutes, earnings: pay(s.minutes), shifts: s.shifts }))
            .sort((a, b) => b.minutes - a.minutes),
          avg_per_worked_day: worked
            ? { minutes: Math.round(totalMin / worked), earnings: pay(totalMin / worked) }
            : { minutes: 0, earnings: 0 },
          longest,
          open_entries: open,
        },
      });
    },

    // ── achievements ──
    async get_achievements() {
      await latency();
      const items = evaluateAchievements(entries, settings.ui_prefs.target_hours, settings.pay_rate, new Date());
      const known = achievementsSeen ?? {};
      return okR('ok', {
        items: withSeen(items, known),
        newly: items.filter((i) => i.met_on && !(i.id in known)).map((i) => i.id),
        first_run: achievementsSeen === null,
      });
    },
    async ack_achievements(ids) {
      await latency();
      if (!Array.isArray(ids) || ids.some((id) => typeof id !== 'string' || !ACHIEVEMENT_IDS.has(id))) {
        return invalid('ids', 'Unknown achievement.');
      }
      if (controls.failSave) return err('save_failed', `Achievements could not be saved: ${saveFailMsg()}`);
      const items = evaluateAchievements(entries, settings.ui_prefs.target_hours, settings.pay_rate, new Date());
      const seen = { ...(achievementsSeen ?? {}) };
      for (const i of items) {
        if (i.met_on && ids.includes(i.id) && !(i.id in seen)) seen[i.id] = i.met_on;
      }
      achievementsSeen = seen;
      return okR('ok');
    },
    async get_pet_stats() {
      await latency();
      return okR('ok', petStats(entries, new Date()));
    },

    // ── import / export / OCR ──
    async export_month(year, m) {
      await wait(400);
      return okR('saved', { path: `C:\\Users\\you\\Documents\\Hours ${monthLabel(year, m)}.xlsx` }, 'Exported (mock)');
    },
    async import_excel() {
      await wait(500);
      const base = new Date();
      base.setDate(base.getDate() - 1);
      const added: WorkEntry[] = [
        { id: `m${++nextId}`, date: toIsoDate(base), job_shift: 'Warehouse', time_in: '12:00', time_out: '16:30' },
      ];
      if (controls.failSave) return err('save_failed', `Import could not be saved.\n\n${saveFailMsg()}`);
      entries.push(...added);
      entries.sort(sortEntries);
      return okR('ok', { imported: added.length, skipped: 1, files: 1, errors: [] });
    },
    async ocr_pick_and_extract() {
      await wait(700);
      if (!dlc.ocr_available) return err('dlc_unavailable', 'Install the DLC to import from images.');
      const d = new Date();
      d.setDate(d.getDate() - 2);
      return okR('ok', {
        candidates: [
          { date: toIsoDate(d), job_shift: 'Sales', time_in: '09:00', time_out: '17:00', raw_line: `${toIsoDate(d)} Sales 09:00-17:00`, confidence: 'ok' },
          { date: toIsoDate(d), job_shift: 'Support', time_in: '17:30', time_out: '2l:00', raw_line: 'Support 17:30-2l:00', confidence: 'uncertain' },
        ],
        errors: [],
      });
    },
    async ocr_save(rows: OcrRow[]) {
      await latency();
      if (controls.failSave) return err('save_failed', `Rows could not be saved.\n\n${saveFailMsg()}`);
      let imported = 0;
      let invalidSkipped = 0;
      for (const r of rows) {
        const date = parseDateInput(r.date);
        const tIn = parseTimeInput(r.time_in);
        if (!date || !tIn) {
          invalidSkipped++;
          continue;
        }
        entries.push({ id: `m${++nextId}`, date, job_shift: r.job_shift, time_in: tIn, time_out: parseTimeInput(r.time_out) ?? '' });
        imported++;
      }
      entries.sort(sortEntries);
      return okR('saved', { imported, skipped: 0, invalid_skipped: invalidSkipped });
    },

    // ── updates & DLC ──
    async check_updates() {
      await wait(600);
      if (q.has('certfail')) return err('network', `Could not check for updates:\n${CERT_FAIL}`);
      const latest = q.has('update') ? '2.1.0' : VERSION;
      const available = latest !== VERSION;
      if (available) emitEvent('update:available', { version: latest, current: VERSION });
      return okR('ok', {
        app: { current: VERSION, latest, available },
        dlc: dlc.version ? { current: dlc.version, latest: dlc.version, available: false } : null,
      });
    },
    async open_download_page() {
      console.info('[mock] would open the releases page');
      return okR('ok');
    },
    async install_update() {
      await wait(300);
      if (q.has('certfail')) return err('update_failed', `The update could not be installed:\n\n${CERT_FAIL}`);
      return err('not_frozen', 'Updates can only be installed from the installed app, not when running from source.');
    },
    async get_dlc_status() {
      return okR('ok', { dlc: { ...dlc } });
    },
    async dlc_install() {
      await wait(1500);
      dlc = { state: 'ok', version: '1.0.2', update_version: null, message: null, ocr_available: true };
      emitEvent('dlc:status', { ...dlc });
      return okR('ok', { verified: true, dlc: { ...dlc } });
    },
    async dlc_remove(confirm) {
      const a = answerFor(confirm, 'remove_dlc');
      if (!a) {
        const opts: ConfirmOption[] = [
          { id: 'remove', label: 'Remove', variant: 'danger' },
          { id: 'cancel', label: 'Cancel', variant: 'neutral' },
        ];
        return needs<'remove_dlc'>({
          kind: 'remove_dlc',
          title: 'Remove DLC?',
          message: 'Remove the DLC? Import from image will no longer be available.',
          options: opts,
          default: 'cancel',
          cancel: 'cancel',
          icon: 'warning',
        });
      }
      if (a.choice !== 'remove') return okR('cancelled', { dlc: { ...dlc } });
      await wait(400);
      dlc = { state: 'missing', version: null, update_version: null, message: null, ocr_available: false };
      emitEvent('dlc:status', { ...dlc });
      return okR('ok', { dlc: { ...dlc } });
    },
  };

  return api;
}
