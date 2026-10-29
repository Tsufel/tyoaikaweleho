// Pure time/date helpers. Mirrors utils.py (and ui/time_picker_popup.nearest_slot)
// so the frontend validates and previews exactly like Python; Python stays
// authoritative on save.

export const LONG_SHIFT_MINUTES = 14 * 60;
export const MIN_SHIFT_SECONDS = 60;
const CONFIRM_AHEAD_MS = 6 * 3600 * 1000;
const DAY_MS = 24 * 3600 * 1000;

export const WEEKDAYS_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const WEEKDAYS_MIN = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
export const MONTHS_SHORT = MONTHS.map((m) => m.slice(0, 3));

const pad2 = (n: number) => String(n).padStart(2, '0');

/** Python int(): optional sign, digits with single underscores, outer whitespace. */
function pyInt(s: string): number | null {
  if (!/^\s*[+-]?\d+(_\d+)*\s*$/.test(s)) return null;
  return parseInt(s.replace(/_/g, '').trim(), 10);
}

const isDigits = (s: string) => /^\d+$/.test(s);

/** Loose time → "HH:MM", or null. '9:30', '9.30', '930', '1345', '9'. */
export function parseTimeInput(raw: string | null | undefined): string | null {
  if (raw == null) return null;
  let t = raw.trim().replace(/\./g, ':');
  if (isDigits(t)) {
    if (t.length <= 2) t = t + ':00';
    else if (t.length === 3) t = t[0] + ':' + t.slice(1);
    else if (t.length === 4) t = t.slice(0, 2) + ':' + t.slice(2);
    else return null;
  }
  const parts = t.split(':');
  if (parts.length !== 2) return null;
  const h = pyInt(parts[0]);
  const m = pyInt(parts[1]);
  if (h === null || m === null) return null;
  if (h >= 0 && h <= 23 && m >= 0 && m <= 59) return `${pad2(h)}:${pad2(m)}`;
  return null;
}

export const isValidTime = (t: string) => parseTimeInput(t) !== null;

function validYmd(y: number, m: number, d: number): boolean {
  if (m < 1 || m > 12 || d < 1) return false;
  return d <= new Date(Date.UTC(y, m, 0)).getUTCDate();
}

function isoFromYmd(y: number, m: number, d: number): string {
  return `${String(y).padStart(4, '0')}-${pad2(m)}-${pad2(d)}`;
}

/** Date of ISO year/week/weekday (1 = Monday). */
function fromIsoWeek(y: number, w: number, wd: number): [number, number, number] | null {
  if (w < 1 || w > 53 || wd < 1 || wd > 7) return null;
  const jan4 = new Date(Date.UTC(y, 0, 4));
  const monday = new Date(jan4.getTime() - ((jan4.getUTCDay() + 6) % 7) * DAY_MS);
  const d = new Date(monday.getTime() + ((w - 1) * 7 + wd - 1) * DAY_MS);
  if (w === 53 && isoWeekOf(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate())[0] !== y) {
    return null;
  }
  return [d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()];
}

/** Python date.fromisoformat (3.11+) subset: YYYY-MM-DD, YYYYMMDD, YYYY-Www[-D], YYYYWww[D]. */
function fromIsoFormat(s: string): [number, number, number] | null {
  let m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s) ?? /^(\d{4})(\d{2})(\d{2})$/.exec(s);
  if (m) {
    const y = +m[1], mo = +m[2], d = +m[3];
    return y >= 1 && validYmd(y, mo, d) ? [y, mo, d] : null;
  }
  m = /^(\d{4})-W(\d{2})(?:-(\d))?$/.exec(s) ?? /^(\d{4})W(\d{2})(\d)?$/.exec(s);
  if (m) return fromIsoWeek(+m[1], +m[2], m[3] ? +m[3] : 1);
  return null;
}

/** Loose date → ISO "YYYY-MM-DD", or null. '2026-6-2', '20260602', '2.6.2026', '2.6.', '2.6'. */
export function parseDateInput(raw: string | null | undefined, today: Date = new Date()): string | null {
  if (raw == null) return null;
  const s = raw.trim();
  let ymd: [number, number, number] | null = null;
  let m = /^(\d{1,2})\.(\d{1,2})(?:\.(\d{4})?)?$/.exec(s);
  if (m) {
    const y = m[3] ? +m[3] : today.getFullYear();
    ymd = [y, +m[2], +m[1]];
  } else if ((m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s))) {
    ymd = [+m[1], +m[2], +m[3]];
  } else {
    ymd = fromIsoFormat(s);
  }
  if (!ymd || ymd[0] < 1 || !validYmd(...ymd)) return null;
  if (ymd[0] < 1900 || ymd[0] > 9999) return null;
  return isoFromYmd(...ymd);
}

/** '20', '20,50', '20.50 €' → number in (0, 10000], else null. */
export function parsePayRate(raw: string): number | null {
  const s = raw.trim().replace(/€/g, '').trim().replace(/,/g, '.');
  if (!/^[+-]?(\d+(_\d+)*)?(\.(\d+(_\d+)*)?)?([eE][+-]?\d+)?$/.test(s) || !/\d/.test(s)) {
    return null;
  }
  const rate = Number(s.replace(/_/g, ''));
  if (!Number.isFinite(rate) || !(rate > 0 && rate <= 10_000)) return null;
  return rate;
}

function toMin(t: string): number | null {
  const m = /^\s*(\d+):(\d+)\s*$/.exec(t);
  return m ? +m[1] * 60 + +m[2] : null;
}

/** Minutes between two HH:MM; wraps past midnight. Bad input → 0. */
export function entryMinutes(timeIn: string, timeOut: string): number {
  const a = toMin(timeIn), b = toMin(timeOut);
  if (a === null || b === null) return 0;
  let diff = b - a;
  if (diff < 0) diff += 24 * 60;
  return diff;
}

export function isOvernight(timeIn: string, timeOut: string): boolean {
  const a = toMin(timeIn), b = toMin(timeOut);
  return a !== null && b !== null && b < a;
}

export const isLongShift = (minutes: number) => minutes > LONG_SHIFT_MINUTES;

/** Start for a picked HH:MM: a time later than now means yesterday. */
export function resolveStartTime(hour: number, minute: number, now: Date): Date {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0);
  if (start.getTime() > now.getTime()) start.setDate(start.getDate() - 1);
  return start;
}

/** True when the next HH:MM is 0–6 h ahead of now (ask: now or yesterday?). */
export function startTimeNeedsConfirm(hour: number, minute: number, now: Date): boolean {
  const target = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0);
  const ahead = (((target.getTime() - now.getTime()) % DAY_MS) + DAY_MS) % DAY_MS;
  return ahead > 0 && ahead < CONFIRM_AHEAD_MS;
}

export function addHours(t: string, hours: number): string {
  const [h, m] = t.split(':').map(Number);
  return `${pad2((((h + hours) % 24) + 24) % 24)}:${pad2(m)}`;
}

/** 480 → '8h 00m'. */
export function formatDuration(minutes: number): string {
  const m = Math.max(0, Math.floor(minutes));
  return `${Math.floor(m / 60)}h ${pad2(m % 60)}m`;
}

/** 480 → '8:00' (table totals). */
export function formatHM(minutes: number): string {
  const m = Math.max(0, Math.floor(minutes));
  return `${Math.floor(m / 60)}:${pad2(m % 60)}`;
}

/** Seconds → 'HH:MM:SS' (hours not capped). */
export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${pad2(Math.floor(s / 3600))}:${pad2(Math.floor(s / 60) % 60)}:${pad2(s % 60)}`;
}

export const formatMoney = (x: number) => `€${(Number.isFinite(x) ? x : 0).toFixed(2)}`;

// ── Time picker slots ───────────────────────────────────────────

export const SLOTS: string[] = Array.from({ length: 48 }, (_, i) => `${pad2(Math.floor(i / 2))}:${i % 2 ? '30' : '00'}`);

/** Index of the half-hour nearest to t (ties round up; 23:50 → 0), or null. */
export function nearestSlot(t: string | null | undefined): number | null {
  const p = t ? parseTimeInput(t) : null;
  if (p === null) return null;
  const [h, m] = p.split(':').map(Number);
  return Math.floor((h * 60 + m + 15) / 30) % SLOTS.length;
}

// ── Dates ────────────────────────────────────────────────────────

export function toIsoDate(d: Date): string {
  return isoFromYmd(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

/** 'YYYY-MM-DD' → local Date at midnight (null if malformed). */
export function fromIsoDate(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m || !validYmd(+m[1], +m[2], +m[3])) return null;
  return new Date(+m[1], +m[2] - 1, +m[3]);
}

/** Local-naive 'YYYY-MM-DDTHH:MM:SS' → Date. */
export function fromIsoDateTime(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/.exec(iso);
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], m[6] ? +m[6] : 0);
}

export function toIsoDateTime(d: Date): string {
  return `${toIsoDate(d)}T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

export const hhmm = (d: Date) => `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;

function isoWeekOf(y: number, m: number, d: number): [number, number] {
  const date = new Date(Date.UTC(y, m - 1, d));
  const wd = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - wd + 3);
  const isoYear = date.getUTCFullYear();
  const firstThu = new Date(Date.UTC(isoYear, 0, 4));
  const week = 1 + Math.round(((date.getTime() - firstThu.getTime()) / DAY_MS - 3 + ((firstThu.getUTCDay() + 6) % 7)) / 7);
  return [isoYear, week];
}

/** (ISO year, ISO week) — utils.week_key. */
export function isoWeek(d: Date): [number, number] {
  return isoWeekOf(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

/** '2026-W39' */
export function weekKey(d: Date): string {
  const [y, w] = isoWeek(d);
  return `${y}-W${pad2(w)}`;
}

/** Python strftime subset: %a %A %d %b %B %Y %m %H %M %S %%. */
export function strftime(d: Date, fmt: string): string {
  const wd = (d.getDay() + 6) % 7;
  return fmt.replace(/%([aAdbBYmHMS%])/g, (_, c: string) => {
    switch (c) {
      case 'a': return WEEKDAYS_SHORT[wd];
      case 'A': return ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][wd];
      case 'd': return pad2(d.getDate());
      case 'b': return MONTHS_SHORT[d.getMonth()];
      case 'B': return MONTHS[d.getMonth()];
      case 'Y': return String(d.getFullYear());
      case 'm': return pad2(d.getMonth() + 1);
      case 'H': return pad2(d.getHours());
      case 'M': return pad2(d.getMinutes());
      case 'S': return pad2(d.getSeconds());
      default: return '%';
    }
  });
}

export const monthLabel = (year: number, month: number) => `${MONTHS[month - 1]} ${year}`;

/** Shift a {year, month} by delta months. */
export function addMonths(year: number, month: number, delta: number): { year: number; month: number } {
  const index = year * 12 + (month - 1) + delta;
  return { year: Math.floor(index / 12), month: (((index % 12) + 12) % 12) + 1 };
}

/** 'on Tue 23 Sep, 09:00–17:00' (main_window._describe). */
export function describeEntry(e: { date: string; time_in: string; time_out: string }): string {
  const d = fromIsoDate(e.date);
  const day = d ? strftime(d, '%a %d %b') : e.date;
  return `on ${day}, ${e.time_in}–${e.time_out}`;
}

/** Default date for a new entry: today when viewing the current month, else the 1st. */
export function defaultEntryDate(view: { year: number; month: number }, today: Date = new Date()): string {
  if (today.getFullYear() === view.year && today.getMonth() + 1 === view.month) return toIsoDate(today);
  return isoFromYmd(view.year, view.month, 1);
}

/** Live duration line of the add/edit modal (EditEntryDialog._update_duration). */
export function durationNote(timeIn: string, timeOut: string): { text: string; tone: 'muted' | 'warning' } {
  const tIn = parseTimeInput(timeIn);
  const outRaw = timeOut.trim();
  const tOut = outRaw ? parseTimeInput(outRaw) : '';
  if (tIn === null || tOut === null) return { text: 'Duration: —', tone: 'muted' };
  if (tOut === '') return { text: 'No time out yet — the shift counts as 0h', tone: 'muted' };
  const minutes = entryMinutes(tIn, tOut);
  let text = `Duration: ${formatDuration(minutes)}`;
  if (isOvernight(tIn, tOut)) text += '  (+1 day)';
  if (isLongShift(minutes)) return { text: text + '  — unusually long', tone: 'warning' };
  return { text, tone: 'muted' };
}

/** Strip the ' +1' overnight marker the table shows after time_out. */
export const stripNextDay = (s: string) => s.replace(/\s*\+1\s*$/, '');
