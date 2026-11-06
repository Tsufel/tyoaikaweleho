// Finnish public holidays: the TypeScript twin of holidays.py, for the Timer
// greeting and the mock API. Python stays authoritative (list_month carries
// `holidays`); tests/fixtures/fi_holidays.json keeps the two in step.

const pad2 = (n: number) => String(n).padStart(2, '0');
const iso = (d: Date) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

/** Western (Gregorian) Easter Sunday, local midnight. */
export function easterSunday(year: number): Date {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const n = h + l - 7 * m + 114;
  return new Date(year, Math.floor(n / 31) - 1, (n % 31) + 1);
}

/** The first Saturday on or after month/day. */
function saturdayFrom(year: number, month: number, day: number): Date {
  const d = new Date(year, month - 1, day);
  return addDays(d, (6 - d.getDay() + 7) % 7);
}

const cache = new Map<number, Record<string, string>>();

/** Every holiday of *year*: ISO date -> Finnish name, in date order. */
export function holidaysInYear(year: number): Record<string, string> {
  const hit = cache.get(year);
  if (hit) return hit;
  const easter = easterSunday(year);
  const midsummer = saturdayFrom(year, 6, 20);
  const days: [Date, string][] = [
    [new Date(year, 0, 1), 'Uudenvuodenpäivä'],
    [new Date(year, 0, 6), 'Loppiainen'],
    [addDays(easter, -2), 'Pitkäperjantai'],
    [easter, 'Pääsiäispäivä'],
    [addDays(easter, 1), '2. pääsiäispäivä'],
    [new Date(year, 4, 1), 'Vappu'],
    [addDays(easter, 39), 'Helatorstai'],
    [addDays(midsummer, -1), 'Juhannusaatto'],
    [midsummer, 'Juhannuspäivä'],
    [saturdayFrom(year, 10, 31), 'Pyhäinpäivä'],
    [new Date(year, 11, 6), 'Itsenäisyyspäivä'],
    [new Date(year, 11, 24), 'Jouluaatto'],
    [new Date(year, 11, 25), 'Joulupäivä'],
    [new Date(year, 11, 26), 'Tapaninpäivä'],
  ];
  const merged = new Map<string, string>();
  for (const [d, name] of days) {
    const k = iso(d);
    const prev = merged.get(k);
    merged.set(k, prev ? `${prev} / ${name}` : name);
  }
  const out = Object.fromEntries([...merged].sort(([a], [b]) => (a < b ? -1 : 1)));
  cache.set(year, out);
  return out;
}

/** ISO date -> name for one month (1-12), like list_month's `holidays`. */
export function holidaysInMonth(year: number, month: number): Record<string, string> {
  const prefix = `${year}-${pad2(month)}-`;
  return Object.fromEntries(Object.entries(holidaysInYear(year)).filter(([k]) => k.startsWith(prefix)));
}

/** The holiday's name when *d* (local date) is one, else null. */
export function holidayName(d: Date): string | null {
  return holidaysInYear(d.getFullYear())[iso(d)] ?? null;
}

/** Mon-Fri and not a public holiday: the days a workday streak counts
 *  (achievements.is_workday). */
export function isWorkday(d: Date): boolean {
  const wd = d.getDay();
  return wd !== 0 && wd !== 6 && holidayName(d) === null;
}

/** The workday before *d*, skipping weekends and holidays. */
export function prevWorkday(d: Date): Date {
  let p = addDays(d, -1);
  while (!isWorkday(p)) p = addDays(p, -1);
  return p;
}
