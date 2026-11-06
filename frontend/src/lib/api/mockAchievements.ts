// Port of achievements.py for the dev mock (mock.ts). Keep the rules in step
// with the Python engine; tests/test_achievements.py is the spec.

import type { Achievement, AchievementTier, PetStats, WorkEntry } from './types';
import { entryMinutes, fromIsoDate, isOvernight, toIsoDate } from '../time';

interface Def {
  id: string;
  tier: AchievementTier;
  goal: number | null;
  unit: string;
  title: string;
  desc: string;
  hidden?: boolean;
  /** Medal art to reuse; defaults to the id. */
  icon?: string;
}

const CATALOGUE: Def[] = [
  { id: 'first_shift', tier: 'bronze', goal: 1, unit: 'shifts', title: 'First shift', desc: 'Save your first shift.' },
  { id: 'hours_10', tier: 'bronze', goal: 10, unit: 'h', title: '10 hours', desc: 'Log 10 hours in total.' },
  { id: 'target_10', tier: 'bronze', goal: 10, unit: 'days', title: 'On target', desc: 'Hit your daily target on 10 days.' },
  { id: 'first_overnight', tier: 'bronze', goal: 1, unit: 'shifts', hidden: true, title: 'Through the night', desc: 'Work a shift past midnight.' },
  { id: 'friday_13', tier: 'bronze', goal: 1, unit: 'shifts', hidden: true, icon: 'night_owl', title: 'Unlucky for some', desc: 'Work a shift on Friday the 13th.' },
  { id: 'leet', tier: 'bronze', goal: 1, unit: 'shifts', hidden: true, icon: 'early_bird', title: '1337', desc: 'Start a shift at exactly 13:37.' },
  { id: 'double_header', tier: 'bronze', goal: 1, unit: 'days', hidden: true, icon: 'target_10', title: 'Double header', desc: 'Work two shifts on the same day.' },
  { id: 'hours_100', tier: 'silver', goal: 100, unit: 'h', title: '100 hours', desc: 'Log 100 hours in total.' },
  { id: 'streak_5', tier: 'silver', goal: 5, unit: 'days', title: 'Full week', desc: "Hit your target on 5 workdays in a row (weekends don't count)." },
  { id: 'weeks_4', tier: 'silver', goal: 4, unit: 'weeks', title: 'Regular', desc: 'Work at least one shift in 4 weeks in a row.' },
  { id: 'early_bird', tier: 'silver', goal: 1, unit: 'shifts', hidden: true, title: 'Early bird', desc: 'Start a shift before 06:00.' },
  { id: 'night_owl', tier: 'silver', goal: 1, unit: 'shifts', hidden: true, title: 'Night owl', desc: 'Keep working past 22:00.' },
  { id: 'earned_1k', tier: 'silver', goal: 1000, unit: '€', title: '€1 000 earned', desc: 'Earn €1 000 in total.' },
  { id: 'hours_250', tier: 'silver', goal: 250, unit: 'h', icon: 'hours_100', title: '250 hours', desc: 'Log 250 hours in total.' },
  { id: 'joulu', tier: 'silver', goal: 1, unit: 'shifts', hidden: true, icon: 'first_overnight', title: 'Joulutonttu', desc: 'Work a shift between Christmas Eve and Boxing Day.' },
  { id: 'hours_500', tier: 'gold', goal: 500, unit: 'h', title: '500 hours', desc: 'Log 500 hours in total.' },
  { id: 'target_50', tier: 'gold', goal: 50, unit: 'days', title: 'Bullseye', desc: 'Hit your daily target on 50 days.' },
  { id: 'marathon_12h', tier: 'gold', goal: 12, unit: 'h', hidden: true, title: 'Marathon', desc: 'Work a single 12-hour shift.' },
  { id: 'earned_10k', tier: 'gold', goal: 10000, unit: '€', title: '€10 000 earned', desc: 'Earn €10 000 in total.' },
  { id: 'shifts_100', tier: 'gold', goal: 100, unit: 'shifts', icon: 'first_shift', title: 'Centurion', desc: 'Save 100 shifts.' },
  { id: 'streak_10', tier: 'gold', goal: 10, unit: 'days', icon: 'streak_5', title: 'Fortnight', desc: "Hit your target on 10 workdays in a row (weekends don't count)." },
  { id: 'weeks_12', tier: 'gold', goal: 12, unit: 'weeks', icon: 'weeks_4', title: 'Seasoned', desc: 'Work at least one shift in 12 weeks in a row.' },
  { id: 'no_days_off', tier: 'gold', goal: 7, unit: 'days', hidden: true, icon: 'weeks_4', title: 'No days off', desc: 'Work every day of one week, Monday to Sunday.' },
  { id: 'one_year', tier: 'gold', goal: 365, unit: 'days', hidden: true, icon: 'target_50', title: 'One year in', desc: 'Work a shift a year after your first one.' },
  { id: 'hours_1000', tier: 'legendary', goal: 1000, unit: 'h', title: '1000 hours', desc: 'Log 1000 hours in total.' },
  { id: 'hours_2500', tier: 'legendary', goal: 2500, unit: 'h', icon: 'hours_1000', title: '2500 hours', desc: 'Log 2500 hours in total.' },
  { id: 'lulz_inferno', tier: 'legendary', goal: null, unit: 'h', hidden: true, title: 'Inferno', desc: 'Work a single shift long enough to reach the ☄️ inferno fire (125% of your target).' },
  { id: 'lulz_blue_overtime', tier: 'legendary', goal: null, unit: 'h', hidden: true, title: 'Blue flame', desc: 'Clock out in blue overtime fire (past your daily target).' },
];

export const ACHIEVEMENT_IDS = new Set(CATALOGUE.map((a) => a.id));

const floorTo = (x: number, places = 1) => Math.floor(x * 10 ** places + 1e-9) / 10 ** places;
const money = (x: number) => Math.round(x * 100) / 100;
const clock = (t: string) => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(t);
  return m ? +m[1] * 60 + +m[2] : null;
};
// Calendar arithmetic, not ms, so DST changes don't shift the day.
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const weekday = (d: Date) => (d.getDay() + 6) % 7; // Mon 0 … Sun 6
const prevWorkday = (d: Date) => {
  let p = addDays(d, -1);
  while (weekday(p) >= 5) p = addDays(p, -1);
  return p;
};

export function evaluateAchievements(
  entries: WorkEntry[],
  targetHours: number,
  payRate: number,
  today: Date,
): Achievement[] {
  const target = Math.max(1, Number.isFinite(targetHours) && targetHours > 0 ? targetHours : 8);
  const targetMin = target * 60;
  const rate = Number.isFinite(payRate) && payRate > 0 ? payRate : 0;
  const todayIso = toIsoDate(today);
  const goals: Record<string, number> = {};
  for (const a of CATALOGUE) goals[a.id] = a.goal ?? 0;
  goals.lulz_inferno = floorTo(target * 1.25, 2);
  goals.lulz_blue_overtime = target;

  const met = new Map<string, string>();
  const hit = (id: string, d: string) => {
    if (!met.has(id)) met.set(id, d);
  };

  const shifts = entries
    .map((e) => ({ e, start: clock(e.time_in), end: clock(e.time_out), d: fromIsoDate(e.date) }))
    .filter((s) => s.start !== null && s.end !== null && s.d && s.e.date <= todayIso)
    .map((s) => ({ ...s, mins: entryMinutes(s.e.time_in, s.e.time_out) }))
    .filter((s) => s.mins > 0)
    .sort((a, b) => (a.e.date < b.e.date ? -1 : a.e.date > b.e.date ? 1 : a.start! - b.start!));

  const firstDay = shifts.length ? shifts[0].d! : today;
  const daysBetween = (a: Date, b: Date) =>
    Math.round((Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) - Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) / 86_400_000);
  let totalMin = 0;
  let longest = 0;
  const dayMin = new Map<string, number>();
  const dayShifts = new Map<string, number>();
  for (const [i, { e, start, mins, d: day }] of shifts.entries()) {
    const d = e.date;
    totalMin += mins;
    longest = Math.max(longest, mins);
    dayMin.set(d, (dayMin.get(d) ?? 0) + mins);
    dayShifts.set(d, (dayShifts.get(d) ?? 0) + 1);
    hit('first_shift', d);
    if (i + 1 >= goals.shifts_100) hit('shifts_100', d);
    for (const id of ['hours_10', 'hours_100', 'hours_250', 'hours_500', 'hours_1000', 'hours_2500'])
      if (totalMin >= goals[id] * 60) hit(id, d);
    for (const id of ['earned_1k', 'earned_10k']) if (rate && money((totalMin / 60) * rate) >= goals[id]) hit(id, d);
    if (isOvernight(e.time_in, e.time_out)) hit('first_overnight', d);
    if (start! < 6 * 60) hit('early_bird', d);
    if (start! + mins > 22 * 60) hit('night_owl', d);
    if (mins >= 12 * 60) hit('marathon_12h', d);
    if (mins >= targetMin * 1.25) hit('lulz_inferno', d);
    if (mins > targetMin) hit('lulz_blue_overtime', d);
    // Calendar Easter eggs, all on the start date.
    if (weekday(day!) === 4 && day!.getDate() === 13) hit('friday_13', d);
    if (day!.getMonth() === 11 && [24, 25, 26].includes(day!.getDate())) hit('joulu', d);
    if (start === 13 * 60 + 37) hit('leet', d);
    if (dayShifts.get(d)! >= 2) hit('double_header', d);
    if (daysBetween(firstDay, day!) >= 365) hit('one_year', d);
  }

  let targetDays = 0;
  let run = 0;
  let bestRun = 0;
  let lastRunDay: string | null = null;
  let weeks = 0;
  let bestWeeks = 0;
  let lastWeek: string | null = null;
  let weekDays = 0;
  let bestWeekDays = 0;
  for (const iso of [...dayMin.keys()].sort()) {
    const d = fromIsoDate(iso)!;
    if (dayMin.get(iso)! >= targetMin) {
      targetDays++;
      if (targetDays >= goals.target_10) hit('target_10', iso);
      if (targetDays >= goals.target_50) hit('target_50', iso);
      if (weekday(d) < 5) {
        run = lastRunDay === toIsoDate(prevWorkday(d)) ? run + 1 : 1;
        lastRunDay = iso;
        bestRun = Math.max(bestRun, run);
        for (const id of ['streak_5', 'streak_10']) if (run >= goals[id]) hit(id, iso);
      }
    } else if (weekday(d) < 5) {
      run = 0;
      lastRunDay = null;
    }
    const monday = toIsoDate(addDays(d, -weekday(d)));
    if (monday !== lastWeek) {
      weeks = lastWeek === toIsoDate(addDays(fromIsoDate(monday)!, -7)) ? weeks + 1 : 1;
      lastWeek = monday;
      bestWeeks = Math.max(bestWeeks, weeks);
      for (const id of ['weeks_4', 'weeks_12']) if (weeks >= goals[id]) hit(id, iso);
      weekDays = 0;
    }
    // every day of one ISO week, Monday to Sunday
    weekDays++;
    bestWeekDays = Math.max(bestWeekDays, weekDays);
    if (weekDays >= goals.no_days_off) hit('no_days_off', iso);
  }

  const hours = floorTo(totalMin / 60);
  const earned = Math.floor(money((totalMin / 60) * rate));
  const longestH = floorTo(longest / 60);
  const cur: Record<string, number> = {
    first_shift: shifts.length, shifts_100: shifts.length,
    hours_10: hours, hours_100: hours, hours_250: hours, hours_500: hours, hours_1000: hours, hours_2500: hours,
    target_10: targetDays, target_50: targetDays,
    streak_5: bestRun, streak_10: bestRun,
    weeks_4: bestWeeks, weeks_12: bestWeeks,
    friday_13: +met.has('friday_13'), joulu: +met.has('joulu'),
    leet: +met.has('leet'), double_header: +met.has('double_header'),
    no_days_off: bestWeekDays,
    one_year: shifts.length ? daysBetween(firstDay, shifts[shifts.length - 1].d!) : 0,
    first_overnight: +met.has('first_overnight'),
    early_bird: +met.has('early_bird'),
    night_owl: +met.has('night_owl'),
    marathon_12h: longestH,
    earned_1k: earned, earned_10k: earned,
    lulz_inferno: longestH, lulz_blue_overtime: longestH,
  };

  return CATALOGUE.map((a) => {
    const goal = goals[a.id];
    const metOn = met.get(a.id) ?? null;
    return {
      id: a.id,
      title: a.title,
      desc: a.desc,
      icon: a.icon ?? a.id,
      tier: a.tier,
      hidden: a.hidden ?? false,
      progress: { cur: metOn ? goal : Math.min(cur[a.id], goal), goal, unit: a.unit },
      met_on: metOn,
    };
  });
}

/** Seen achievements stay unlocked on their stored date (achievements.with_seen). */
export function withSeen(items: Achievement[], seen: Record<string, string>): Achievement[] {
  return items.map((i) =>
    i.id in seen ? { ...i, met_on: seen[i.id], progress: { ...i.progress, cur: i.progress.goal } } : i,
  );
}

/** Port of achievements.pet_stats: lifetime minutes, and minutes per start date
 *  for the last 56 days (today included). */
export function petStats(entries: WorkEntry[], today: Date): PetStats {
  const todayIso = toIsoDate(today);
  const first = toIsoDate(addDays(today, -55));
  let lifetime = 0;
  const days: Record<string, number> = {};
  for (const e of entries) {
    if (clock(e.time_in) === null || clock(e.time_out) === null || !fromIsoDate(e.date) || e.date > todayIso) continue;
    const mins = entryMinutes(e.time_in, e.time_out);
    if (mins <= 0) continue;
    lifetime += mins;
    if (e.date >= first) days[e.date] = (days[e.date] ?? 0) + mins;
  }
  return { lifetime_minutes: lifetime, days };
}
