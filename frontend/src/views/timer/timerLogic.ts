import { fromIsoDateTime, hhmm, strftime, toIsoDate } from '../../lib/time';

export const IDLE_TEXT = 'Press START (F5) to begin tracking';

/** SVG ring geometry (viewBox units), shared with the fire layer. */
export const RING = { size: 240, r: 100, stroke: 14 } as const;
/** Radius of the inner disc holding the clock (viewBox units); the fire never draws inside it. */
export const RING_INNER = RING.r - RING.stroke / 2 - 9;

/** Fraction of the daily target done; > 1 in overtime. */
export function ringProgress(elapsedSeconds: number, targetHours: number): number {
  const target = Math.max(1, targetHours || 8) * 3600;
  return Math.max(0, elapsedSeconds) / target;
}

// violet → cyan → teal (target reached) → lime → amber (double target)
const HUE_STOPS: [number, number][] = [
  [0, 265],
  [0.5, 195],
  [1, 165],
  [1.5, 95],
  [2, 32],
];

/** Halo / ring hue for a progress fraction. */
export function haloHue(progress: number): number {
  const p = Math.max(0, progress);
  if (p >= HUE_STOPS[HUE_STOPS.length - 1][0]) return HUE_STOPS[HUE_STOPS.length - 1][1];
  for (let i = 1; i < HUE_STOPS.length; i++) {
    const [p1, h1] = HUE_STOPS[i];
    if (p <= p1) {
      const [p0, h0] = HUE_STOPS[i - 1];
      return Math.round(h0 + ((p - p0) / (p1 - p0)) * (h1 - h0));
    }
  }
  return HUE_STOPS[0][1];
}

/** Overtime cap of fireIntensity; same as MAX_INTENSITY in fx/fire/fireSim (not imported: keeps the fx chunk lazy). */
const FIRE_MAX = 1.6;

/** Lulz fire strength: 0.45 at the start, 1 at the target (sqrt curve, ≈0.64 after 1 h of 8),
 *  then +0.6 per target length of overtime up to 1.6. */
export function fireIntensity(elapsedSeconds: number, targetHours: number): number {
  const p = ringProgress(elapsedSeconds, targetHours);
  if (!(p > 0)) return 0.45;
  if (p <= 1) return 0.45 + 0.55 * Math.sqrt(p);
  return Math.min(FIRE_MAX, 1 + (p - 1) * 0.6);
}

export type FireBadge = { emoji: string; text: string } | null;

/** "🔥 on fire" streak badge for Lulz mode. */
export function fireBadge(running: boolean, elapsedSeconds: number, targetHours: number): FireBadge {
  if (!running) return null;
  const p = ringProgress(elapsedSeconds, targetHours);
  if (elapsedSeconds < 15 * 60) return { emoji: '🔥', text: 'warming up' };
  if (p < 1) return { emoji: '🔥', text: 'on fire' };
  if (p < 1.25) return { emoji: '🔥🔥', text: 'unstoppable' };
  return { emoji: '☄️', text: 'inferno' };
}

/** "Started 09:12 (yesterday)" — v1.3 TimerPanel._running_text, without the job. */
export function startedText(startIso: string | null, now: Date = new Date()): string {
  const start = startIso ? fromIsoDateTime(startIso) : null;
  if (!start) return 'Started —';
  let text = `Started ${hhmm(start)}`;
  const a = Date.UTC(start.getFullYear(), start.getMonth(), start.getDate());
  const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((b - a) / 86_400_000);
  if (days === 1) text += ' (yesterday)';
  else if (days) text += ` (${strftime(start, '%a %d %b')})`;
  return text;
}

/** Full v1.3 status line: "Started 09:12 (yesterday)  ·  Support  ·  running…". */
export function runningText(startIso: string | null, job: string, now: Date = new Date()): string {
  return `${startedText(startIso, now)}  ·  ${job || '—'}  ·  running…`;
}

/** Elapsed seconds → 'HH:MM:SS' split into glyphs for the rolling clock. */
export function clockGlyphs(seconds: number): string[] {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(h)}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`.split('');
}

/** Spoken form for screen readers: "2 hours 5 minutes". */
export function spokenDuration(seconds: number): string {
  const m = Math.floor(Math.max(0, seconds) / 60);
  const h = Math.floor(m / 60);
  const mm = m % 60;
  const parts: string[] = [];
  if (h) parts.push(`${h} hour${h === 1 ? '' : 's'}`);
  parts.push(`${mm} minute${mm === 1 ? '' : 's'}`);
  return parts.join(' ');
}

/** Hour tick angles (degrees from 12 o'clock) for a target of n hours. */
export function hourTicks(targetHours: number): number[] {
  const n = Math.min(24, Math.max(1, Math.round(targetHours || 8)));
  return Array.from({ length: n }, (_, i) => (360 * i) / n);
}

/** Point on the ring for a progress fraction (0 = top, clockwise), viewBox units. */
export function ringPoint(progress: number, r: number = RING.r, size: number = RING.size): { x: number; y: number } {
  const a = (progress % 1) * Math.PI * 2 - Math.PI / 2;
  return { x: size / 2 + r * Math.cos(a), y: size / 2 + r * Math.sin(a) };
}

/** Recovery dialog date line: 'Tue 2026-09-23'. */
export function recoveryDate(startIso: string): string {
  const d = fromIsoDateTime(startIso);
  return d ? `${strftime(d, '%a')} ${toIsoDate(d)}` : startIso;
}

/** '3h 07m' like the v1.3 recovery dialog (hours uncapped). */
export function elapsedHM(fromMs: number, nowMs: number = Date.now()): string {
  const m = Math.max(0, Math.floor((nowMs - fromMs) / 60_000));
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`;
}

// ── Start dial: drag the idle ring to back-date the start ─────────────────────

/** Furthest the dial can back-date a start (a later HH:MM would mean tomorrow). */
export const DIAL_MAX_MIN = 23 * 60 + 55;
export const DIAL_STEP_MIN = 5;
/** A picked start falls back to the live clock after this long untouched. */
export const DIAL_RESET_MS = 30_000;
const MIN_MS = 60_000;

/** Pointer position → ring fraction 0…1 (0 = 12 o'clock, clockwise). */
export function pointerFraction(x: number, y: number, cx: number, cy: number): number {
  const a = Math.atan2(x - cx, cy - y) / (Math.PI * 2);
  return a < 0 ? a + 1 : a;
}

/** Turn a raw 0…1 angle into laps continuing from `prev`, so dragging past
 *  12 o'clock keeps counting instead of jumping back to zero. At either end
 *  the dial is a stop: it stays put until the pointer comes back near it.
 *  `fresh` (a new press) jumps to the nearest in-range lap instead. */
export function unwrapLaps(prev: number, raw: number, maxLaps: number, fresh = false): number {
  if (fresh) {
    let best = Math.min(raw, maxLaps);
    for (let v = raw; v <= maxLaps; v += 1) if (Math.abs(v - prev) < Math.abs(best - prev)) best = v;
    return best;
  }
  const v = Math.round(prev - raw) + raw;
  if ((prev <= 0 || prev >= maxLaps) && Math.abs(v - prev) > 0.25) return prev;
  return Math.min(maxLaps, Math.max(0, v));
}

/** Where Python puts an HH:MM start (utils.resolve_start_time): today, or
 *  yesterday when that is later than now. */
function resolveWall(ms: number, nowMs: number): number {
  const p = new Date(ms);
  const d = new Date(nowMs);
  d.setHours(p.getHours(), p.getMinutes(), 0, 0);
  if (d.getTime() > nowMs) d.setDate(d.getDate() - 1);
  return d.getTime();
}

/** Clamp a picked start onto the 5-minute grid, within the dial's range.
 *  null means "now" (the live clock). */
export function snapStart(ms: number, nowMs: number): number | null {
  const step = DIAL_STEP_MIN * MIN_MS;
  const snapped = Math.round(ms / step) * step;
  if (snapped >= nowMs - MIN_MS / 2) return null;
  const earliest = Math.ceil((nowMs - DIAL_MAX_MIN * MIN_MS) / step) * step;
  // only offer starts the HH:MM sent to Python lands on exactly (around DST
  // changes the clock and real elapsed time disagree by an hour)
  let v = Math.max(earliest, snapped);
  while (resolveWall(v, nowMs) !== v) {
    v += step;
    if (v >= nowMs - MIN_MS / 2) return null;
  }
  return v;
}

/** Step the picked start by `deltaMin` (negative = earlier). */
export function nudgeStart(picked: number | null, deltaMin: number, nowMs: number): number | null {
  if (picked == null) {
    if (deltaMin >= 0) return null;
    // first step back from "now" lands on the previous 5-minute mark
    const step = DIAL_STEP_MIN * MIN_MS;
    const prev = Math.floor((nowMs - MIN_MS / 2 - 1) / step) * step;
    return snapStart(prev + (deltaMin + DIAL_STEP_MIN) * MIN_MS, nowMs);
  }
  return snapStart(picked + deltaMin * MIN_MS, nowMs);
}

/** Start time for a dial position given as ring laps of the daily target. */
export function startFromLaps(laps: number, targetHours: number, nowMs: number): number | null {
  const target = Math.max(1, targetHours || 8) * 60;
  return snapStart(nowMs - laps * target * MIN_MS, nowMs);
}

/** 'yesterday' when the picked start is on an earlier calendar day than now. */
export function dialDay(pickedMs: number, nowMs: number): '' | 'yesterday' {
  return toIsoDate(new Date(pickedMs)) === toIsoDate(new Date(nowMs)) ? '' : 'yesterday';
}

/** "1h 15m ago" / "25m ago" for a picked start. */
export function agoText(pickedMs: number, nowMs: number): string {
  const m = Math.max(0, Math.floor((nowMs - pickedMs) / MIN_MS));
  const h = Math.floor(m / 60);
  return h ? `${h}h ${String(m % 60).padStart(2, '0')}m ago` : `${m}m ago`;
}
