"""All v1.3 UI rules (timer panel, main window, entries table, edit dialog,
settings view) as plain methods returning result envelopes. No pywebview,
no dialogs: the api layer passes file paths in and shows the confirms.
See docs/V2_UI_API.md."""
import copy
import json
import os
import sys
import threading
from datetime import date, datetime, timedelta

import storage
import timer as timer_module
from services import dlc, net
from timer import WorkTimer
from utils import (MIN_SHIFT_SECONDS, entry_minutes, format_duration, format_rate,
                   is_long_shift, is_overnight, overlapping, parse_date_input,
                   parse_pay_rate, parse_time_input, resolve_start_time,
                   start_far_behind, start_time_needs_confirm, week_key)
from webapp import results as R
from webapp.results import Stale, answer, describe, entry_row, money, opt, stored_entry_dict

MAX_ENTRY_MINUTES = 24 * 60
RECOVERY_LIMIT = timedelta(hours=8)


def _session_start(session: dict) -> datetime | None:
    try:
        start = datetime.fromisoformat(session["start"])
    except (TypeError, ValueError, KeyError):
        return None
    if start.tzinfo is not None:
        # via the epoch, so a start in a repeated DST hour keeps its fold
        return datetime.fromtimestamp(start.timestamp())
    if session.get("start_fold") == 1:
        start = start.replace(fold=1)
    return start
MAX_STATS_DAYS = 3700

_LOCKED_HINT = "Close any program that may be locking data.json"


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _epoch_ms(dt: datetime) -> int:
    return int(timer_module._epoch(dt) * 1000)


def _elapsed_minutes(start: datetime, end: datetime) -> int:
    """Whole real minutes from start to end, right across a DST change."""
    return max(0, int(timer_module.elapsed_between(start, end) // 60))


def _wall_minutes(start: datetime, end: datetime) -> int:
    """Whole clock minutes from start to end, the way the HH:MM entry
    counts them (seconds dropped on both ends)."""
    a = start.replace(second=0, microsecond=0)
    b = end.replace(second=0, microsecond=0)
    return max(0, int((b - a).total_seconds() // 60))


def _fingerprint(e) -> str:
    return f"{e.id}|{e.date}|{e.job_shift}|{e.time_in}|{e.time_out}"


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _ver_tuple(v) -> tuple:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0, 0, 0)


class ShiftController:
    def __init__(self, timer: WorkTimer | None = None, clock=datetime.now):
        self._lock = threading.RLock()
        self._timer = timer if timer is not None else WorkTimer()
        self._clock = clock
        self._update: tuple[str, str, str | None] | None = None
        self.dlc_update_version: str | None = None
        self._last_export: str | None = None

    # ── helpers ──────────────────────────────────────────────────

    def _now(self) -> datetime:
        return self._clock()

    def _session_pending(self) -> bool:
        """An unfinished shift waits in session.json. One that names an
        entry already saved (STOP saved it, then session.json couldn't be
        removed) doesn't count: recovery() just tidies it away."""
        if self._timer.is_running:
            return False
        session = timer_module.load_saved_session()
        return session is not None and not self._already_saved(session)

    @staticmethod
    def _setting(getter, fallback):
        # data.json may be locked/corrupt; the timer state must still render
        try:
            return getter()
        except (OSError, ValueError) as exc:
            storage.append_error_log(f"timer_state: {getter.__name__} failed: {exc}")
            return fallback

    def timer_state(self) -> dict:
        with self._lock:
            t = self._timer
            running = t.is_running and t.start_dt is not None
            default_js = self._setting(storage.get_default_job_shift, "")
            return {
                "running": running,
                "start_iso": _iso(t.start_dt) if running else None,
                "start_epoch_ms": _epoch_ms(t.start_dt) if running else None,
                "job_shift": t.job_shift if running else default_js,
                "default_job_shift": default_js,
                "default_start_time": self._setting(storage.get_default_start_time, ""),
                "pay_rate": self._setting(storage.get_pay_rate, 0.0),
                "recovery_pending": self._session_pending(),
            }

    def running_start(self) -> datetime | None:
        """The running shift's start, or None; no disk reads (window title)."""
        with self._lock:
            t = self._timer
            return t.start_dt if t.is_running else None

    def _start(self, job_shift: str, start: datetime) -> dict | None:
        """Start the timer; an error result if session.json can't be written."""
        try:
            self._timer.start(job_shift, start_time=start)
        except OSError as exc:
            self._timer = type(self._timer)()
            return R.error("save_failed",
                           f"The shift could not be started:\n\n{exc}\n\n"
                           f"{_LOCKED_HINT} and try again.",
                           timer=self.timer_state())
        return None

    def _end_shift(self):
        self._timer.stop()
        self._clear_session()

    @staticmethod
    def _read_session() -> dict | None:
        """session.json's content; {} when it can't be parsed, None when it
        is missing or can't be read right now (kept for a later try)."""
        path = timer_module._SESSION_FILE
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as exc:
            storage.append_error_log(f"could not read session.json: {exc}")
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _mark_saved(entry_id: str):
        try:
            timer_module.mark_session_saved(entry_id)
        except OSError as exc:
            storage.append_error_log(f"could not mark session.json as saved: {exc}")

    @staticmethod
    def _already_saved(session: dict) -> bool:
        """True when session.json names the entry it was saved as and that
        entry exists (a matching date/time alone proves nothing: a second
        shift may start at the same minute)."""
        sid = session.get("saved_entry_id")
        if not isinstance(sid, str) or not sid:
            return False
        try:
            entries = storage.load_all_entries()
        except (OSError, ValueError):
            return False
        return any(e.id == sid for e in entries)

    @staticmethod
    def _set_aside_session():
        """session.json can't be understood: keep it under another name (it
        may still tell the user when a lost shift began) instead of
        deleting it."""
        path = timer_module._SESSION_FILE
        kept = os.path.join(os.path.dirname(path),
                            f"session.bad-{datetime.now():%Y%m%d-%H%M%S}.json")
        try:
            os.replace(path, kept)
            storage.append_error_log(f"session.json could not be read; kept as {kept}")
        except OSError as exc:
            storage.append_error_log(f"session.json could not be read or set aside: {exc}")

    @staticmethod
    def _clear_session():
        try:
            timer_module.clear_saved_session()
        except OSError as exc:
            storage.append_error_log(f"could not remove session.json: {exc}")

    def _find(self, entry_id: str):
        return next((e for e in storage.load_all_entries() if e.id == entry_id), None)

    @staticmethod
    def _not_found() -> dict:
        return R.error("not_found", "That entry no longer exists.")

    @staticmethod
    def _long_entry_confirm(t_in: str, t_out: str, minutes: int,
                            token: str | None = None, **payload) -> dict:
        overnight = is_overnight(t_in, t_out)
        return R.needs_confirm(
            "long_entry", "Long shift",
            f"{t_in}–{t_out} is {format_duration(minutes)}"
            f"{' (ending the next day)' if overnight else ''}.\n\nSave it anyway?",
            [opt("save", "Save anyway", "primary"), opt("cancel", "Cancel", "neutral")],
            default="save", cancel="cancel", icon="warning", token=token,
            details={"time_in": t_in, "time_out": t_out, "overnight": overnight,
                     "elapsed_minutes": minutes}, **payload)

    def _backdate_confirm(self, t: str, earlier: datetime, now: datetime) -> dict:
        minutes = _elapsed_minutes(earlier, now)
        day = "today" if earlier.date() == now.date() else "yesterday"
        return R.needs_confirm(
            "start_backdate", "Start that far back?",
            f"It's {now:%H:%M} now. Starting from {t} {day} puts "
            f"{format_duration(minutes)} on the timer straight away.\n\n"
            f"Start the shift now, or from {t} {day} ({earlier:%a %d %b})?",
            [opt("now", f"Start now ({now:%H:%M})", "primary"),
             opt("earlier", f"From {day} {t}", "neutral"),
             opt("cancel", "Cancel", "neutral")],
            default="now", cancel="cancel", icon="warning",
            details={"start_iso": _iso(earlier), "elapsed_minutes": minutes},
            timer=self.timer_state())

    @staticmethod
    def _overlaps(entry, before=None) -> list:
        """Saved entries that *entry* overlaps. When editing (*before* is the
        stored version), overlaps it already had aren't reported again."""
        others = storage.load_all_entries()
        hits = overlapping(entry, others)
        if before is not None and hits:
            known = {o.id for o in overlapping(before, others)}
            if all(o.id in known for o in hits):
                return []
        return hits

    @staticmethod
    def _overlap_lines(hits) -> str:
        lines = [f"• {o.job_shift or '—'} {describe(o)}" for o in hits[:3]]
        if len(hits) > 3:
            lines.append(f"• and {len(hits) - 3} more")
        return "\n".join(lines)

    def _overlap_confirm(self, hits) -> dict:
        return R.needs_confirm(
            "overlap", "Overlapping shift",
            f"This shift overlaps {_plural(len(hits), 'another entry', f'{len(hits)} other entries')}:"
            f"\n\n{self._overlap_lines(hits)}\n\n"
            "Both would count on the timesheet. Save it anyway?",
            [opt("save", "Save anyway", "neutral"), opt("cancel", "Go back", "primary")],
            default="cancel", cancel="cancel", icon="warning",
            details={"overlaps": len(hits)})

    def _overlap_warning(self, entry) -> dict:
        """Extra payload for a shift saved without asking (timer stop,
        recovery): the UI shows it as a warning toast."""
        try:
            hits = self._overlaps(entry)
        except (OSError, ValueError):
            return {}
        if not hits:
            return {}
        return {"overlap_warning":
                f"This shift overlaps {_plural(len(hits), 'another entry', f'{len(hits)} other entries')}:"
                f"\n{self._overlap_lines(hits)}"}

    # ── app / lifecycle ──────────────────────────────────────────

    def changelog(self, current_version: str) -> list[dict] | None:
        """Versions newer than the last one run, newest first (or None), and
        records *current_version* as seen."""
        import changelog as cl
        last = storage.get_last_seen_version()
        if last != current_version:   # an unchanged version writes nothing
            try:
                storage.set_last_seen_version(current_version)
            except OSError as exc:
                storage.append_error_log(f"could not store last_seen_version: {exc}")
        if last is None or last == current_version:
            return None
        newer = [v for v in cl.CHANGELOG if _ver_tuple(v) > _ver_tuple(last)]
        if not newer:
            return None
        newer.sort(key=_ver_tuple, reverse=True)
        return [{"version": v, "items": list(cl.CHANGELOG[v])} for v in newer]

    @staticmethod
    def _take_data_recovery() -> dict | None:
        """The note left by storage when a damaged data.json was replaced
        by a backup, shown to the user once."""
        note, storage.last_recovery = storage.last_recovery, None
        return note

    def bootstrap(self, version: str, frozen: bool = False, dev: bool = False) -> dict:
        with self._lock:
            changelog = self.changelog(version)
            recovery = self.recovery()
            now = self._now()
            return R.ok(data={
                "version": version, "frozen": bool(frozen), "dev": bool(dev),
                "today": now.date().isoformat(), "now_epoch_ms": _epoch_ms(now),
                "settings": self._settings(), "shifts": storage.get_job_shift_list(),
                "timer": self.timer_state(), "dlc": self.dlc_status(),
                "changelog": changelog, "recovery": recovery,
                "data_recovery": self._take_data_recovery(),
                "month": {"year": now.year, "month": now.month},
                "error_log": storage.ERROR_LOG, "data_dir": storage.DATA_DIR,
                "shifts_file": storage.SHIFTS_FILE,
            })

    def ensure_shifts_file(self) -> str:
        with self._lock:
            storage._ensure_shifts_file()
            return storage.SHIFTS_FILE

    def close_app(self, confirm=None) -> dict:
        """Success results carry quit=True: the api layer then saves the
        window placement and destroys the window."""
        with self._lock:
            t = self._timer
            if not t.is_running:
                return R.ok(quit=True)
            token, pressed = self._press_token(confirm, t.start_dt, self._now())
            try:
                choice = answer(confirm, "close_running", token)
            except Stale:
                return R.stale(timer=self.timer_state())
            if choice is None:
                minutes = _elapsed_minutes(t.start_dt, pressed)
                return R.needs_confirm(
                    "close_running", "Shift still running",
                    f"A shift is running (started {t.start_dt:%H:%M}, "
                    f"{format_duration(minutes)} ago).\n\n"
                    "Stop, save & close  →  save the shift, then close\n"
                    "Close anyway  →  the shift will be recovered on next open\n"
                    "Stay open  →  keep working",
                    [opt("stop_close", "Stop, save & close", "primary"),
                     opt("close", "Close anyway", "neutral"),
                     opt("cancel", "Stay open", "neutral")],
                    default="stop_close", cancel="cancel", icon="warning", token=token,
                    details={"start_iso": _iso(t.start_dt), "elapsed_minutes": minutes})
            if choice == "close":
                return R.ok(quit=True)
            if choice != "stop_close":
                return R.cancelled(timer=self.timer_state())
            result = self.timer_stop("close", confirm)
            if result["status"] in ("saved", "discarded"):
                result["quit"] = True
            return result

    # ── timer ────────────────────────────────────────────────────

    def get_timer(self) -> dict:
        return R.ok(timer=self.timer_state())

    def timer_start(self, mode: str, time: str | None = None,
                    job_shift: str | None = None, confirm=None) -> dict:
        with self._lock:
            if self._timer.is_running:
                return R.error("already_running", "A shift is already running.",
                               timer=self.timer_state())
            if self._session_pending():
                return R.error("recovery_pending",
                               "An unfinished shift from last time needs to be "
                               "saved, resumed or discarded first.",
                               timer=self.timer_state())
            try:
                typed = storage.clean_job_shift(job_shift)
            except ValueError as exc:
                return R.invalid("job_shift", str(exc), timer=self.timer_state())
            js = (typed or storage.get_default_job_shift() or "").strip() or "—"
            now = self._now().replace(microsecond=0)
            if mode == "now":
                start = now
            elif mode == "at":
                t = parse_time_input(time or "")
                if t is None:
                    return R.invalid("time", "Start time must be a valid time (e.g. 09:30).",
                                     timer=self.timer_state())
                h, m = map(int, t.split(":"))
                earlier = resolve_start_time(h, m, now)
                if not start_time_needs_confirm(h, m, now):
                    start = earlier
                    if start_far_behind(earlier, now):
                        choice = answer(confirm, "start_backdate")
                        if choice is None:
                            return self._backdate_confirm(t, earlier, now)
                        if choice == "now":
                            start = now
                        elif choice != "earlier":
                            return R.cancelled(timer=self.timer_state())
                else:
                    choice = answer(confirm, "start_ahead")
                    if choice is None:
                        day = "today" if earlier.date() == now.date() else "yesterday"
                        return R.needs_confirm(
                            "start_ahead", "Start time hasn't come yet",
                            f"It's {now:%H:%M} now, so the next {t} is still ahead.\n\n"
                            f"Start the shift now, or from {t} {day} ({earlier:%a %d %b})?",
                            [opt("now", f"Start now ({now:%H:%M})", "primary"),
                             opt("earlier", f"From {day} {t}", "neutral"),
                             opt("cancel", "Cancel", "neutral")],
                            default="now", cancel="cancel",
                            details={"start_iso": _iso(earlier)},
                            timer=self.timer_state())
                    if choice == "now":
                        start = now
                    elif choice == "earlier":
                        start = earlier
                    else:
                        return R.cancelled(timer=self.timer_state())
            else:
                return R.invalid("mode", "Unknown start mode.", timer=self.timer_state())
            failed = self._start(js, start)
            return failed or R.ok(timer=self.timer_state())

    def timer_stop(self, source: str = "button", confirm=None) -> dict:
        with self._lock:
            t = self._timer
            if not t.is_running:
                return R.ok(timer=self.timer_state())
            try:
                return self._stop(source, confirm)
            except Stale:
                return R.stale(timer=self.timer_state())

    @staticmethod
    def _press_token(confirm, start: datetime, now: datetime) -> tuple[str, datetime]:
        """The token for a stop's confirms and the moment STOP was pressed.
        The token is `start_iso@press_iso`, so the press time comes back with
        the answers and the shift ends at the press minute, not when the
        question was answered. A plain `start_iso` answer (older callers)
        stops at *now*; a token naming another start doesn't match (stale)."""
        base = _iso(start)
        answers = [a for a in confirm if isinstance(a, dict)] if isinstance(confirm, (list, tuple)) else []
        for a in reversed(answers):
            tok = a.get("token")
            if isinstance(tok, str) and tok.startswith(base + "@"):
                try:
                    pressed = datetime.fromisoformat(tok[len(base) + 1:])
                except ValueError:
                    continue
                if pressed.tzinfo is None and start <= pressed <= now:
                    return tok, pressed
        if any(a.get("token") == base for a in answers):
            return base, now
        return f"{base}@{_iso(now)}", now

    def _stop(self, source: str, confirm) -> dict:
        t = self._timer
        start, job_shift = t.start_dt, t.job_shift
        token, now = self._press_token(confirm, start, self._now())
        elapsed = timer_module.elapsed_between(start, now)
        minutes = max(0, int(elapsed // 60))
        details = {"start_iso": _iso(start), "elapsed_minutes": minutes}
        # the entry keeps HH:MM only, so the limits go by whole clock minutes:
        # 09:00:30 → 09:00:10 next day is 1439 elapsed but 1440 on the sheet
        wall = _wall_minutes(start, now)
        long = is_long_shift(wall)

        if source == "shortcut":
            choice = answer(confirm, "stop_shift", token)
            if choice is None:
                return R.needs_confirm(
                    "stop_shift", "Stop shift?",
                    f"Stop the shift started at {start:%H:%M} "
                    f"({format_duration(minutes)} ago) and save it?",
                    [opt("stop", "Yes", "primary"), opt("keep", "No", "neutral")],
                    default="stop", cancel="keep",
                    icon="warning" if long else "question", token=token, details=details,
                    timer=self.timer_state())
            if choice != "stop":
                return R.cancelled(timer=self.timer_state())

        if elapsed < MIN_SHIFT_SECONDS:
            self._end_shift()
            return R.discarded("Shift under a minute — not saved", timer=self.timer_state())

        time_out = None
        if wall >= MAX_ENTRY_MINUTES:
            capped = start + timedelta(hours=8)
            choice = answer(confirm, "over_24h", token)
            if choice is None:
                return R.needs_confirm(
                    "over_24h", "Shift over 24 hours",
                    f"This shift has been running for {format_duration(minutes)} "
                    f"(since {start:%a %d %b %H:%M}), longer than one entry can hold."
                    f"\n\nSave it ending at the 8-hour mark ({capped:%H:%M}) and fix "
                    "the end time in the table, or discard it?",
                    [opt("save", f"Save until {capped:%H:%M}", "primary"),
                     opt("discard", "Discard", "danger"),
                     opt("keep", "Keep running", "neutral")],
                    default="keep", cancel="keep", icon="warning", token=token,
                    details={**details, "capped_end": f"{capped:%H:%M}"},
                    timer=self.timer_state())
            if choice == "discard":
                sure = answer(confirm, "discard_shift", token)
                if sure is None:
                    return self._discard_confirm(token, details, timer=self.timer_state())
                if sure == "discard":
                    self._end_shift()
                    return R.discarded("Shift discarded", timer=self.timer_state())
                return R.cancelled(timer=self.timer_state())
            if choice != "save":
                return R.cancelled(timer=self.timer_state())
            time_out = f"{capped:%H:%M}"
        elif source == "button" and long:
            choice = answer(confirm, "long_shift", token)
            if choice is None:
                return R.needs_confirm(
                    "long_shift", "Long shift",
                    f"This shift has been running for {format_duration(minutes)} "
                    f"(since {start:%a %d %b %H:%M}).\n\nStop and save it?\n\n"
                    "No keeps the timer running.",
                    [opt("stop", "Yes", "primary"), opt("keep", "No", "neutral")],
                    default="stop", cancel="keep", icon="warning", token=token,
                    details=details, timer=self.timer_state())
            if choice != "stop":
                return R.cancelled(timer=self.timer_state())

        return self._save_stopped(start, job_shift, time_out or now.strftime("%H:%M"))

    def _save_stopped(self, start: datetime, job_shift: str, time_out: str) -> dict:
        """Stop the running shift and save it as start–time_out."""
        t = self._timer
        entry = storage.WorkEntry(
            id=storage.new_entry_id(), date=start.strftime("%Y-%m-%d"),
            job_shift=job_shift, time_in=start.strftime("%H:%M"),
            time_out=time_out)
        t.stop()
        self._mark_saved(entry.id)
        try:
            storage.save_entry(entry)
        except OSError as exc:
            # session.json is still on disk; keep the shift running so the
            # user can press STOP again
            try:
                t.start(job_shift, start_time=start)
            except OSError:
                pass
            return R.error("save_failed",
                           "The shift could not be saved and is still running.\n\n"
                           f"{exc}\n\n{_LOCKED_HINT} and press STOP again.",
                           timer=self.timer_state())
        self._clear_session()
        return R.saved(entry=entry_row(entry), timer=self.timer_state(),
                       **self._overlap_warning(entry))

    @staticmethod
    def _discard_confirm(token: str, details: dict | None = None, **payload) -> dict:
        return R.needs_confirm(
            "discard_shift", "Discard shift", "Discard this shift? It will not be saved.",
            [opt("discard", "Discard", "danger"), opt("cancel", "Cancel", "neutral")],
            default="cancel", cancel="cancel", icon="warning", token=token,
            details=details, **payload)

    def timer_discard(self, confirm=None) -> dict:
        with self._lock:
            t = self._timer
            if not t.is_running:
                return R.error("not_running", "No shift is running.", timer=self.timer_state())
            token = _iso(t.start_dt)
            try:
                choice = answer(confirm, "discard_shift", token)
            except Stale:
                return R.stale(timer=self.timer_state())
            if choice is None:
                return self._discard_confirm(token, {"start_iso": token},
                                             timer=self.timer_state())
            if choice != "discard":
                return R.cancelled(timer=self.timer_state())
            self._end_shift()
            return R.discarded("Shift discarded", timer=self.timer_state())

    # ── running shift: stop at a past time, fix the start or job ─────

    def timer_stop_at(self, end: str, confirm=None) -> dict:
        """Stop and save the running shift as ending at *end* (HH:MM), the
        first such time after the start. A time still ahead is refused."""
        with self._lock:
            t = self._timer
            if not t.is_running:
                return R.error("not_running", "No shift is running.", timer=self.timer_state())
            t_out = parse_time_input(end or "")
            if t_out is None:
                return R.invalid("end", "End time must be a valid time (e.g. 17:00).",
                                 timer=self.timer_state())
            start, job_shift = t.start_dt, t.job_shift
            t_in = start.strftime("%H:%M")
            minutes = entry_minutes(t_in, t_out)
            if minutes == 0:
                return R.invalid("end", f"End time must be after the start ({t_in}).",
                                 timer=self.timer_state())
            now = self._now()
            if _wall_minutes(start, now) < minutes:
                return R.invalid("end", f"{t_out} hasn't come yet (it's {now:%H:%M} now).",
                                 timer=self.timer_state())
            if is_long_shift(minutes):
                token = _iso(start)
                try:
                    choice = answer(confirm, "long_entry", token)
                except Stale:
                    return R.stale(timer=self.timer_state())
                if choice is None:
                    return self._long_entry_confirm(t_in, t_out, minutes, token,
                                                    timer=self.timer_state())
                if choice != "save":
                    return R.cancelled(timer=self.timer_state())
            return self._save_stopped(start, job_shift, t_out)

    def timer_adjust(self, start_iso: str, time: str | None = None,
                     job_shift: str | None = None, confirm=None) -> dict:
        """Move the running shift's start to *time* (the last HH:MM at or
        before now) and/or change its job. *start_iso* is the start the user
        saw; another one means the shift changed meanwhile."""
        with self._lock:
            t = self._timer
            if not t.is_running:
                return R.error("not_running", "No shift is running.", timer=self.timer_state())
            old = t.start_dt
            if start_iso != _iso(old):
                return R.stale(timer=self.timer_state())
            try:
                typed = storage.clean_job_shift(job_shift)
            except ValueError as exc:
                return R.invalid("job_shift", str(exc), timer=self.timer_state())
            job = t.job_shift if job_shift is None else (typed or "—")
            start = old
            if time is not None:
                tm = parse_time_input(time)
                if tm is None:
                    return R.invalid("time", "Start time must be a valid time (e.g. 09:30).",
                                     timer=self.timer_state())
                now = self._now().replace(microsecond=0)
                h, m = map(int, tm.split(":"))
                if start_time_needs_confirm(h, m, now):
                    return R.invalid("time", f"{tm} hasn't come yet (it's {now:%H:%M} now).",
                                     timer=self.timer_state())
                start = resolve_start_time(h, m, now)
                if start.replace(second=0) == old.replace(second=0, microsecond=0):
                    start = old
                elif start < old and start_far_behind(start, now):
                    try:
                        choice = answer(confirm, "start_backdate", start_iso)
                    except Stale:
                        return R.stale(timer=self.timer_state())
                    if choice is None:
                        day = "today" if start.date() == now.date() else "yesterday"
                        return R.needs_confirm(
                            "start_backdate", "Move the start that far back?",
                            f"It's {now:%H:%M} now. Starting from {tm} {day} puts "
                            f"{format_duration(_wall_minutes(start, now))} on the timer.",
                            [opt("earlier", f"From {day} {tm}", "primary"),
                             opt("cancel", f"Keep {old:%H:%M}", "neutral")],
                            default="cancel", cancel="cancel", icon="warning",
                            token=start_iso,
                            details={"start_iso": _iso(start),
                                     "elapsed_minutes": _wall_minutes(start, now)},
                            timer=self.timer_state())
                    if choice != "earlier":
                        return R.cancelled(timer=self.timer_state())
            if start == old and job == t.job_shift:
                return R.ok(timer=self.timer_state())
            try:
                t.set_start(start, job)
            except OSError as exc:
                return R.error("save_failed",
                               f"The change could not be saved:\n\n{exc}\n\n"
                               f"{_LOCKED_HINT} and try again.",
                               timer=self.timer_state())
            return R.ok(timer=self.timer_state())

    # ── crash recovery ───────────────────────────────────────────

    def recovery(self) -> dict | None:
        """The unfinished shift in session.json (Recovery), or None. An
        unreadable session file is removed."""
        with self._lock:
            if self._timer.is_running:
                return None
            session = self._read_session()
            if session is None:
                return None
            start = _session_start(session)
            if start is None:
                self._set_aside_session()
                return None
            job_shift = session.get("job_shift")
            if self._already_saved(session):
                # saved by STOP or a recovery save whose session.json
                # couldn't be removed: offering it again would duplicate it
                storage.append_error_log(
                    f"session.json from {_iso(start)} was already saved; removed it")
                self._clear_session()
                return None
            now = self._now()
            over_limit = (timer_module.elapsed_between(start, now)
                          >= RECOVERY_LIMIT.total_seconds())
            suggested = start + RECOVERY_LIMIT if over_limit else now
            return {
                "start_iso": _iso(start), "start_epoch_ms": _epoch_ms(start),
                "job_shift": job_shift if isinstance(job_shift, str) else "?",
                "elapsed_minutes": _elapsed_minutes(start, now),
                "over_limit": over_limit, "suggested_end": suggested.strftime("%H:%M"),
            }

    # get_recovery: re-offer recovery without re-running bootstrap
    def get_recovery(self) -> dict:
        """The pending recovery and the timer, re-read without bootstrap's
        writes. Also hands over a data.json repair note left since then."""
        with self._lock:
            return R.ok(recovery=self.recovery(), timer=self.timer_state(),
                        data_recovery=self._take_data_recovery())

    def recovery_resolve(self, action: str, end: str | None = None, confirm=None) -> dict:
        with self._lock:
            rec = self.recovery()
            if rec is None:
                return R.ok(timer=self.timer_state(), recovery=None)
            # session.json again: rec's start_iso has no fold for a start in
            # the repeated DST hour
            start = (_session_start(self._read_session() or {})
                     or datetime.fromisoformat(rec["start_iso"]))
            token = rec["start_iso"]

            if action == "resume":
                failed = self._start(rec["job_shift"], start)
                if failed:
                    failed["recovery"] = rec
                    return failed
                return R.ok(timer=self.timer_state(), recovery=None)

            if action == "save":
                t_out = parse_time_input(end or "")
                if t_out is None:
                    return R.invalid("end", "End time must be a valid time (e.g. 17:00).",
                                     timer=self.timer_state(), recovery=rec)
                t_in = start.strftime("%H:%M")
                minutes = entry_minutes(t_in, t_out)
                if minutes == 0:
                    return R.invalid("end", f"End time must be after the start ({t_in}).",
                                     timer=self.timer_state(), recovery=rec)
                if is_long_shift(minutes):
                    try:
                        choice = answer(confirm, "long_entry", token)
                    except Stale:
                        return R.stale(timer=self.timer_state(), recovery=rec)
                    if choice is None:
                        return self._long_entry_confirm(t_in, t_out, minutes, token,
                                                        timer=self.timer_state(), recovery=rec)
                    if choice != "save":
                        return R.cancelled(timer=self.timer_state(), recovery=rec)
                entry = storage.WorkEntry(
                    id=storage.new_entry_id(), date=start.strftime("%Y-%m-%d"),
                    job_shift=rec["job_shift"], time_in=t_in, time_out=t_out)
                self._mark_saved(entry.id)
                try:
                    storage.save_entry(entry)
                except OSError as exc:
                    return R.error("save_failed",
                                   f"The shift could not be saved:\n\n{exc}\n\n"
                                   f"{_LOCKED_HINT} and try again, or resume the "
                                   "shift for now.",
                                   timer=self.timer_state(),
                                   recovery={**rec, "suggested_end": t_out})
                self._clear_session()
                return R.saved(entry=entry_row(entry), timer=self.timer_state(),
                               recovery=None, **self._overlap_warning(entry))

            if action == "discard":
                try:
                    choice = answer(confirm, "discard_shift", token)
                except Stale:
                    return R.stale(timer=self.timer_state(), recovery=rec)
                if choice is None:
                    return self._discard_confirm(
                        token, {"start_iso": token, "elapsed_minutes": rec["elapsed_minutes"]},
                        timer=self.timer_state(), recovery=rec)
                if choice != "discard":
                    return R.cancelled(timer=self.timer_state(), recovery=rec)
                self._clear_session()
                return R.discarded("Shift discarded", timer=self.timer_state(),
                                   recovery=None)

            return R.invalid("action", "Unknown recovery action.",
                             timer=self.timer_state(), recovery=rec)

    # ── entries ──────────────────────────────────────────────────

    def list_month(self, year: int, month: int) -> dict:
        try:
            first = date(int(year), int(month), 1)
        except (TypeError, ValueError):
            return R.invalid("month", "Not a valid month.")
        with self._lock:
            entries = sorted(storage.load_month(first.year, first.month),
                             key=lambda e: (e.date, e.time_in))
            rate = storage.get_pay_rate()
            # an overnight shift on the last day of the previous month can
            # overlap the 1st, so the neighbouring days are compared too
            lo = (first - timedelta(days=1)).isoformat()
            hi = (date(first.year + first.month // 12, first.month % 12 + 1, 1)).isoformat()
            nearby = [e for e in storage.load_all_entries() if lo <= e.date <= hi]
        rows = []
        for e in entries:
            row = entry_row(e)
            hits = overlapping(e, nearby)
            row["overlap"] = bool(hits)
            # which shifts it clashes with, so the list can name and jump to them
            row["overlap_with"] = [{"id": o.id, "date": o.date, "job_shift": o.job_shift,
                                    "time_in": o.time_in, "time_out": o.time_out}
                                   for o in hits]
            rows.append(row)
        weeks: dict[tuple[int, int], dict] = {}
        for row in rows:
            try:
                key = week_key(date.fromisoformat(row["date"]))
            except ValueError:
                continue
            w = weeks.setdefault(key, {"key": f"{key[0]}-W{key[1]:02d}", "iso_year": key[0],
                                       "week": key[1], "entry_ids": [], "minutes": 0,
                                       "earnings": 0.0})
            w["entry_ids"].append(row["id"])
            w["minutes"] += row["minutes"] or 0
        for w in weeks.values():
            w["earnings"] = money(w["minutes"] / 60 * rate)
        total = sum(r["minutes"] or 0 for r in rows)
        return R.ok(data={
            "year": first.year, "month": first.month, "label": first.strftime("%B %Y"),
            "pay_rate": rate, "entries": rows,
            "weeks": [weeks[k] for k in sorted(weeks)],
            "total_minutes": total, "earnings": money(total / 60 * rate),
        })

    def get_entry(self, entry_id: str) -> dict:
        with self._lock:
            entry = self._find(entry_id)
        return R.ok(entry=entry_row(entry)) if entry else self._not_found()

    def save_entry(self, draft: dict, confirm=None) -> dict:
        draft = draft if isinstance(draft, dict) else {}
        d = parse_date_input(str(draft.get("date") or ""))
        if d is None:
            return R.invalid("date", "Enter the date as YYYY-MM-DD or D.M.YYYY "
                                     "(e.g. 2026-09-23 or 23.9.2026).")
        t_in = parse_time_input(str(draft.get("time_in") or ""))
        if t_in is None:
            return R.invalid("time_in", "Time In must be a valid time (e.g. 09:30).")
        out_raw = str(draft.get("time_out") or "").strip()
        t_out = parse_time_input(out_raw) if out_raw else ""
        if t_out is None:
            return R.invalid("time_out", "Time Out must be a valid time (e.g. 17:00).")
        try:
            job_shift = storage.clean_job_shift(draft.get("job_shift"))
        except ValueError as exc:
            return R.invalid("job_shift", str(exc))
        if t_out:
            minutes = entry_minutes(t_in, t_out)
            if is_long_shift(minutes):
                choice = answer(confirm, "long_entry")
                if choice is None:
                    return self._long_entry_confirm(t_in, t_out, minutes)
                if choice != "save":
                    return R.cancelled()
        entry = storage.WorkEntry(
            id=str(draft.get("id") or "") or storage.new_entry_id(), date=d,
            job_shift=job_shift,
            time_in=t_in, time_out=t_out)
        with self._lock:
            choice = answer(confirm, "overlap")
            if choice is not None and choice != "save":
                return R.cancelled()
            try:
                # the reads hit data.json too: a locked file gets the same
                # save_failed message as the write
                # editing keeps what a newer version stored on the entry
                stored = self._find(entry.id) if draft.get("id") else None
                if stored is not None:
                    entry.extra = dict(stored.extra)
                if choice is None:
                    hits = self._overlaps(entry, stored)
                    if hits:
                        return self._overlap_confirm(hits)
                storage.save_entry(entry)
            except OSError as exc:
                return R.error("save_failed",
                               f"The entry could not be saved:\n\n{exc}\n\n"
                               f"{_LOCKED_HINT} and press Save again.")
        return R.saved(entry=entry_row(entry))

    def update_entry_field(self, entry_id: str, field: str, value: str,
                           confirm=None) -> dict:
        if field not in ("time_in", "time_out"):
            return R.invalid("field", "Only Time In and Time Out can be edited here.")
        with self._lock:
            try:
                entry = self._find(entry_id)
            except OSError as exc:
                return self._field_save_failed(exc)
            if entry is None:
                return self._not_found()
            original = getattr(entry, field)
            text = str(value or "").strip()
            token = text.split()[0] if text else ""   # drops a " +1" suffix
            parsed = parse_time_input(token) if token else None
            if parsed is None:
                if text == original:
                    return R.ok(unchanged=True)
                return R.invalid(field, "Invalid time, not saved")
            if parsed == original:
                return R.ok(unchanged=True)
            before = copy.copy(entry)
            setattr(entry, field, parsed)
            if entry.time_in and entry.time_out:
                minutes = entry_minutes(entry.time_in, entry.time_out)
                if is_long_shift(minutes):
                    choice = answer(confirm, "long_entry")
                    if choice is None:
                        return self._long_entry_confirm(entry.time_in, entry.time_out,
                                                        minutes)
                    if choice != "save":
                        return R.cancelled()
            choice = answer(confirm, "overlap")
            if choice is not None and choice != "save":
                return R.cancelled()
            try:
                if choice is None:
                    hits = self._overlaps(entry, before)
                    if hits:
                        return self._overlap_confirm(hits)
                storage.update_entry(entry)
            except OSError as exc:
                return self._field_save_failed(exc)
            return R.saved(entry=entry_row(entry))

    @staticmethod
    def _field_save_failed(exc) -> dict:
        return R.error("save_failed",
                       f"The change could not be saved:\n\n{exc}\n\n"
                       "Close any program using data.json and try again.")

    def delete_entry(self, entry_id: str, confirm=None) -> dict:
        with self._lock:
            entry = self._find(entry_id)
            if entry is None:
                return self._not_found()
            desc = describe(entry)
            try:
                choice = answer(confirm, "delete_entry", _fingerprint(entry))
            except Stale:
                return R.stale()
            if choice is None:
                return R.needs_confirm(
                    "delete_entry", "Delete entry", f"Delete the shift {desc}?",
                    [opt("delete", "Delete", "danger"), opt("cancel", "Cancel", "neutral")],
                    default="cancel", cancel="cancel", icon="warning",
                    token=_fingerprint(entry), details={"description": desc})
            if choice != "delete":
                return R.cancelled()
            try:
                storage.delete_entry(entry.id)
            except OSError as exc:
                return R.error("save_failed",
                               f"The entry could not be deleted:\n\n{exc}\n\n"
                               f"{_LOCKED_HINT} and try again.")
            return R.ok(f"Deleted {desc}.", deleted=stored_entry_dict(entry), description=desc)

    def restore_entry(self, entry: dict) -> dict:
        if not isinstance(entry, dict) or not all(
                isinstance(entry.get(k), str) for k in ("id", "date", "time_in")):
            return R.invalid("entry", "That is not a saved entry.")
        # a date nothing can read would hide the entry from every month
        if not entry["id"] or parse_date_input(entry["date"]) is None:
            return R.invalid("entry", "That is not a saved entry.")
        # keys a newer version wrote (a break, a note) come back too; a
        # restored entry is never a tombstone
        extra = {k: v for k, v in entry.items()
                 if isinstance(k, str) and k not in storage.ENTRY_FIELDS and k != "deleted"}
        try:
            json.dumps(extra)
        except (TypeError, ValueError):
            return R.invalid("entry", "That is not a saved entry.")
        restored = storage.WorkEntry(**{
            k: str(entry.get(k) or "") for k in storage.ENTRY_FIELDS}, extra=extra)
        desc = describe(restored)
        with self._lock:
            try:
                storage.save_entry(restored)
            except OSError as exc:
                return R.error("save_failed", f"The entry could not be restored:\n\n{exc}",
                               description=desc)
        return R.saved(f"Restored {desc}.", entry=entry_row(restored), description=desc)

    # ── shifts & settings ────────────────────────────────────────

    def _settings(self) -> dict:
        rate = storage.get_pay_rate()
        fmt = storage.get_export_format()
        return {
            "appearance": storage.get_appearance_mode(),
            "default_start_time": storage.get_default_start_time(),
            "pay_rate": rate, "pay_rate_text": format_rate(rate),
            "default_job_shift": storage.get_default_job_shift(),
            "export_format": fmt if fmt in storage.EXPORT_FORMATS else "Simple",
            "export_include_pay": storage.get_export_include_pay(),
            **storage.get_sheet_names(),
            "ui_prefs": storage.get_ui_prefs(),
        }

    def get_settings(self) -> dict:
        with self._lock:
            return R.ok(settings=self._settings(), shifts=storage.get_job_shift_list())

    def save_settings(self, draft: dict) -> dict:
        draft = draft if isinstance(draft, dict) else {}
        t = parse_time_input(str(draft.get("default_start_time") or ""))
        if t is None:
            return R.invalid("default_start_time",
                             "Default start time must be a valid time (e.g. 09:30).")
        rate = parse_pay_rate(str(draft.get("pay_rate") or ""))
        if rate is None:
            return R.invalid("pay_rate",
                             "Pay rate must be a positive number (e.g. 20 or 20,50).")
        values = {
            "default_start_time": t, "pay_rate": rate,
            "default_job_shift": str(draft.get("default_job_shift") or "").strip(),
            "export_include_pay": bool(draft.get("export_include_pay")),
        }
        fmt = draft.get("export_format")
        if fmt is not None:
            if fmt not in storage.EXPORT_FORMATS:
                return R.invalid("export_format", "Export format must be Simple or Full.")
            values["export_format"] = fmt
        if draft.get("appearance") in storage.APPEARANCE_MODES:
            values["appearance_mode"] = draft["appearance"]
        for key in storage.SHEET_NAME_KEYS:  # optional: left out = unchanged
            if key in draft:
                problem = storage._sheet_name_error(key, draft[key])
                if problem:
                    return R.invalid(key, "Names can't contain control characters."
                                     if "control" in problem else
                                     f"Keep names to at most {storage.SHEET_NAME_MAX} characters.")
                values[key] = draft[key]
        prefs = draft.get("ui_prefs")
        if prefs is not None:
            invalid = self._check_prefs(prefs)
            if invalid:
                return invalid
            values["ui_prefs"] = prefs
        with self._lock:
            try:
                storage.save_settings(values)
            except OSError as exc:
                return R.error("save_failed", f"Settings could not be written:\n\n{exc}")
            return R.saved(settings=self._settings(), shifts=storage.get_job_shift_list())

    @staticmethod
    def _check_prefs(prefs) -> dict | None:
        try:
            storage.merge_ui_prefs(None, prefs)
        except ValueError as exc:
            if isinstance(prefs, dict) and "target_hours" in prefs and "target_hours" in str(exc):
                return R.invalid("target_hours",
                                 "Daily target must be between 1 and 24 hours.")
            if isinstance(prefs, dict) and "pet_name" in prefs and "pet_name" in str(exc):
                if "control characters" in str(exc):
                    return R.invalid("pet_name", "Pet names can't contain control characters.")
                return R.invalid("pet_name", "Give your pet a name of at most 24 characters.")
            return R.invalid("ui_prefs", str(exc))
        return None

    def save_ui_prefs(self, prefs: dict) -> dict:
        invalid = self._check_prefs(prefs)
        if invalid:
            return invalid
        with self._lock:
            try:
                storage.set_ui_prefs(prefs)
            except OSError as exc:
                return R.error("save_failed", f"Settings could not be written:\n\n{exc}")
            return R.saved(settings=self._settings())

    def add_job_shift(self, name: str) -> dict:
        try:
            js = storage.clean_job_shift(name)
        except ValueError as exc:
            return R.invalid("name", str(exc))
        if not js:
            return R.invalid("name", "Enter a shift name.")
        with self._lock:
            try:
                added = storage.add_job_shift(js)
            except OSError as exc:
                return R.error("save_failed", f"The shift list could not be written:\n\n{exc}")
            shifts = storage.get_job_shift_list()
        if not added:
            return R.ok(f"'{js}' is already in the shift list.", added=False, shifts=shifts)
        return R.ok(added=True, shifts=shifts)

    # ── your data: backups & restore (Settings → Your data) ──────

    def list_backups(self) -> dict:
        with self._lock:
            return R.ok(backups=storage.list_backups(), data_dir=storage.DATA_DIR,
                        backups_dir=storage.backups_dir())

    def backup_now(self) -> dict:
        with self._lock:
            try:
                path = storage.manual_backup()
            except OSError as exc:
                return R.error("save_failed", f"The backup could not be written:\n\n{exc}")
            backups = storage.list_backups()
        if not path:
            return R.ok("Nothing to back up yet: no shifts have been saved.",
                        backup=None, backups=backups)
        name = os.path.basename(path)
        return R.saved(f"Backed up to backups\\{name}.", backup=name, backups=backups)

    @staticmethod
    def _backup_token(b: dict) -> str:
        return f"{b['name']}|{b['size']}|{b['saved_at']}"

    def restore_backup(self, name, confirm=None) -> dict:
        """Swap a listed backup in for data.json, after a pre-restore copy
        of the current file. A running shift is untouched (it lives in
        session.json) and is saved into the restored data when stopped."""
        with self._lock:
            b = next((x for x in storage.list_backups() if x["name"] == name), None) \
                if isinstance(name, str) else None
            if b is None:
                return R.invalid("name", "That backup no longer exists.")
            if not b["ok"]:
                return R.invalid("name", "That backup can't be read, so it can't be restored.")
            token = self._backup_token(b)
            try:
                choice = answer(confirm, "restore_backup", token)
            except Stale:
                return R.stale()
            if choice is None:
                try:
                    current = len(storage.load_all_entries())
                except (OSError, storage.DataFileCorrupt):
                    current = None
                when = datetime.fromisoformat(b["saved_at"]).strftime("%a %d %b %Y, %H:%M")
                n = b["entries"]
                now_part = "" if current is None else \
                    f" You have {current} {_plural(current, 'shift', 'shifts')} now."
                return R.needs_confirm(
                    "restore_backup", "Restore backup",
                    f"Replace your shifts and settings with the copy from {when} "
                    f"({n} {_plural(n, 'shift', 'shifts')})?{now_part}\n\n"
                    "Your current data is copied to the backups folder first, "
                    "so you can go back.",
                    [opt("restore", "Restore", "danger"), opt("cancel", "Cancel", "neutral")],
                    default="cancel", cancel="cancel", icon="warning", token=token,
                    details={"name": b["name"], "entries": n, "current_entries": current,
                             "saved_at": b["saved_at"]})
            if choice != "restore":
                return R.cancelled()
            try:
                safety = storage.restore_backup(name)
            except LookupError:
                return R.invalid("name", "That backup can't be read, so it can't be restored.")
            except OSError as exc:
                return R.error("save_failed", f"The backup could not be restored, nothing "
                                              f"was changed:\n\n{exc}\n\n{_LOCKED_HINT}.")
            safety_name = os.path.basename(safety) if safety else None
            msg = f"Restored the backup from {b['saved_at'][:10]}."
            if safety_name:
                msg += f" Your previous data is in backups\\{safety_name}."
            return R.saved(msg, restored=b["name"], safety_copy=safety_name,
                           settings=self._settings(), shifts=storage.get_job_shift_list(),
                           timer=self.timer_state(), backups=storage.list_backups())

    # ── stats ────────────────────────────────────────────────────

    def get_stats(self, start_iso: str, end_iso: str, granularity: str = "day") -> dict:
        import stats
        try:
            start = date.fromisoformat(str(start_iso))
            end = date.fromisoformat(str(end_iso))
        except ValueError:
            return R.invalid("range", "Pick a valid date range.")
        if end < start or (end - start).days > MAX_STATS_DAYS:
            return R.invalid("range", "Pick a range of at most about ten years, "
                                      "with the end after the start.")
        if granularity not in stats.GRANULARITIES:
            return R.invalid("granularity", "Group by day, week or month.")
        with self._lock:
            entries = storage.load_all_entries()
            rate = storage.get_pay_rate()
        return R.ok(data=stats.summarize(entries, start, end, granularity, rate))

    def get_stats_span(self) -> dict:
        """First and last entry date, for the All time range. Read-only."""
        import stats
        with self._lock:
            entries = storage.load_all_entries()
        first, last = stats.span(entries)
        return R.ok(first=first, last=last)

    # ── achievements ─────────────────────────────────────────────

    def _evaluate_achievements(self) -> tuple[list[dict], dict | None]:
        import achievements
        with self._lock:
            entries = storage.load_all_entries()
            rate = storage.get_pay_rate()
            target = storage.get_ui_prefs()["target_hours"]
            seen = storage.get_achievements_seen()
        items = achievements.evaluate(entries, target, rate, self._now().date())
        return items, seen

    def get_achievements(self) -> dict:
        """items: every achievement (seen ones stay unlocked); newly: met but not
        yet acknowledged. first_run: nothing was ever acknowledged, so the UI
        shows one summary toast for `newly` instead of one per unlock."""
        import achievements
        items, seen = self._evaluate_achievements()
        known = seen or {}
        return R.ok(items=achievements.with_seen(items, known),
                    newly=achievements.newly(items, known), first_run=seen is None)

    def ack_achievements(self, ids) -> dict:
        """Store *ids* as celebrated. Ids that are not met right now are skipped;
        an empty list still ends the first run."""
        import achievements
        if (not isinstance(ids, list)
                or not all(isinstance(i, str) and i in achievements.IDS for i in ids)):
            return R.invalid("ids", "Unknown achievement.")
        items, _seen = self._evaluate_achievements()
        met = {i["id"]: i["met_on"] for i in items if i["met_on"]}
        with self._lock:
            try:
                storage.add_achievements_seen({i: met[i] for i in ids if i in met})
            except OSError as exc:
                return R.error("save_failed", f"Achievements could not be saved:\n\n{exc}")
        return R.ok()

    def get_pet_stats(self) -> dict:
        """lifetime_minutes and days {iso: minutes} for the last 8 weeks; the
        frontend derives the pet's energy, level and pose from them."""
        import achievements
        with self._lock:
            entries = storage.load_all_entries()
        return R.ok(**achievements.pet_stats(entries, self._now().date()))

    # Personal records (Hall of fame in the Achievements sheet).
    def get_records(self) -> dict:
        """Personal records derived from the entries (records.py). Read-only."""
        import records
        with self._lock:
            entries = storage.load_all_entries()
            target = storage.get_ui_prefs()["target_hours"]
        return R.ok(**records.records(entries, target, self._now().date()))

    # ── import / export / OCR ────────────────────────────────────

    @staticmethod
    def export_filename(year: int, month: int) -> str:
        return f"Hours {date(int(year), int(month), 1):%B %Y}.xlsx"

    def export_month(self, year: int, month: int, path: str | None) -> dict:
        try:
            date(int(year), int(month), 1)
        except (TypeError, ValueError):
            return R.invalid("month", "Not a valid month.")
        if not path:
            return R.cancelled()
        import excel_export
        with self._lock:
            entries = storage.load_month(int(year), int(month))
            fmt = storage.get_export_format()
            include_pay = storage.get_export_include_pay()
            rate = storage.get_pay_rate()
            names = storage.get_sheet_names()
        try:
            excel_export.export_month(entries=entries, year=int(year), month=int(month),
                                      save_path=path, fmt=fmt, include_pay=include_pay,
                                      pay_rate=rate, **names)
        except PermissionError:
            return R.error("file_locked",
                           f"Could not write:\n{path}\n\n"
                           "The file is probably open in Excel — close it and try again.")
        except Exception as exc:
            return R.error("internal", f"Could not export:\n\n{exc}")
        self._last_export = path
        return R.saved(f"Timesheet saved to:\n{path}", path=path)

    # ── export a date range (CSV or Simple workbook) ──

    EXPORT_RANGE_KINDS = ("xlsx", "csv")

    @staticmethod
    def _export_range_args(start_iso, end_iso, kind) -> tuple[date, date, str] | dict:
        if kind not in ShiftController.EXPORT_RANGE_KINDS:
            return R.invalid("kind", "Export as xlsx or csv.")
        try:
            start = date.fromisoformat(str(start_iso))
            end = date.fromisoformat(str(end_iso))
        except ValueError:
            return R.invalid("range", "Pick a valid date range.")
        if end < start or (end - start).days > MAX_STATS_DAYS:
            return R.invalid("range", "Pick a range of at most about ten years, "
                                      "with the end after the start.")
        return start, end, kind

    @staticmethod
    def export_range_filename(start_iso, end_iso, kind) -> str | None:
        """'Hours 1.1.–31.12.2026.csv', or None when the arguments are invalid."""
        import excel_export
        args = ShiftController._export_range_args(start_iso, end_iso, kind)
        if isinstance(args, dict):
            return None
        start, end, kind = args
        return f"Hours {excel_export.range_label(start, end)}.{kind}"

    def export_range(self, start_iso, end_iso, kind, path: str | None) -> dict:
        args = self._export_range_args(start_iso, end_iso, kind)
        if isinstance(args, dict):
            return args
        if not path:
            return R.cancelled()
        start, end, kind = args
        import excel_export
        with self._lock:
            entries = storage.load_all_entries()
            include_pay = storage.get_export_include_pay()
            rate = storage.get_pay_rate()
        try:
            excel_export.export_range(entries, start, end, path, kind=kind,
                                      include_pay=include_pay, pay_rate=rate)
        except PermissionError:
            return R.error("file_locked",
                           f"Could not write:\n{path}\n\n"
                           "The file is probably open in Excel — close it and try again.")
        except Exception as exc:
            return R.error("internal", f"Could not export:\n\n{exc}")
        self._last_export = path
        return R.saved(f"Hours saved to:\n{path}", path=path)

    def last_export(self) -> str | None:
        """The file the last successful export wrote (for "Show in folder";
        the UI never passes a path of its own)."""
        return self._last_export

    def import_excel(self, paths) -> dict:
        paths = [p for p in (paths or []) if p]
        if not paths:
            return R.cancelled()
        import import_excel
        from openpyxl.utils.exceptions import InvalidFileException
        imported = skipped = 0
        errors = []
        notes = []
        with self._lock:
            for path in paths:
                name = os.path.basename(path)
                report = {}
                try:
                    imp, skp = import_excel.import_from_file(path, report)
                    imported += imp
                    skipped += skp
                except InvalidFileException:
                    errors.append(f"{name}: this isn't an .xlsx workbook. "
                                  "Open it in Excel and save it as .xlsx first.")
                    continue
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
                    continue
                if imp or skp:
                    continue
                if report.get("unreadable"):
                    notes.append(f"{name}: found dates, but the start times weren't "
                                 "readable times (e.g. 9:30 or 9.30).")
                else:
                    notes.append(f"No timesheet rows found in {name}: dates go in "
                                 "column A, times in B/C (or C/D with a shift in B).")
        n = len(paths)
        msg = (f"Imported {imported} {_plural(imported, 'entry', 'entries')}"
               f" from {n} {_plural(n, 'file', 'files')}.")
        if skipped:
            msg += f"\n{skipped} {_plural(skipped, 'duplicate', 'duplicates')} skipped."
        if notes:
            msg += "\n\n" + "\n".join(notes)
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors)
        return R.ok(msg, imported=imported, skipped=skipped, files=n, errors=errors,
                    notes=notes)

    @staticmethod
    def _dlc_unavailable() -> dict:
        return R.error("dlc_unavailable", "The Image OCR DLC is not installed.")

    def ocr_extract(self, paths, module=None) -> dict:
        """Runs the OCR without holding the lock (it only reads images)."""
        paths = [p for p in (paths or []) if p]
        if not paths:
            return R.cancelled()
        mod = module or dlc.module()
        if mod is None:
            return self._dlc_unavailable()
        candidates, errors = [], []
        for path in paths:
            try:
                found = mod.extract_entries_from_image(path)
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")
                continue
            for c in found:
                conf = c.get("_confidence")
                candidates.append({
                    "date": str(c.get("date") or ""),
                    "job_shift": str(c.get("job_shift") or ""),
                    "time_in": str(c.get("time_in") or ""),
                    "time_out": str(c.get("time_out") or ""),
                    "raw_line": str(c.get("_raw_line") or ""),
                    "confidence": conf if conf in ("ok", "uncertain") else "uncertain",
                })
        if errors and not candidates:
            return R.error("ocr_failed", "\n".join(errors), errors=errors)
        if not candidates:
            return R.ok("No timesheet entries could be detected in the image(s).",
                        candidates=[], errors=errors)
        return R.ok(candidates=candidates, errors=errors)

    def ocr_save(self, rows, module=None) -> dict:
        mod = module or dlc.module()
        if mod is None:
            return self._dlc_unavailable()
        valid, invalid_skipped = [], 0
        for r in rows or []:
            row = {k: str((r or {}).get(k) or "").strip()
                   for k in ("date", "job_shift", "time_in", "time_out")}
            if row["date"] and row["time_in"]:
                valid.append(row)
            else:
                invalid_skipped += 1
        with self._lock:
            try:
                imported, skipped = mod.save_confirmed_entries(valid)
            except OSError as exc:
                return R.error("save_failed", f"The entries could not be saved:\n\n{exc}")
        msg = f"Imported {imported} {_plural(imported, 'entry', 'entries')}."
        if skipped:
            msg += f"\n{skipped} {_plural(skipped, 'duplicate', 'duplicates')} skipped."
        if invalid_skipped:
            msg += (f"\n{invalid_skipped} row(s) had no date or start time "
                    "and were skipped.")
        return R.saved(msg, imported=imported, skipped=skipped,
                       invalid_skipped=invalid_skipped)

    # ── updates & DLC ────────────────────────────────────────────

    def dlc_status(self) -> dict:
        import updater
        st = dlc.load_status()
        ok = st["state"] == "ok"
        newer = self.dlc_update_version
        if not (ok and newer and updater._is_newer(newer, st["version"] or "0.0.0")):
            newer = None
        message = None
        if st["state"] == "incompatible":
            reason = f" ({st['error']})" if st["error"] else ""
            message = (f"The installed Image OCR DLC could not be loaded{reason}. "
                       "Reinstall or remove it.")
        return {"state": st["state"], "version": st["version"], "update_version": newer,
                "message": message, "ocr_available": ok}

    def get_dlc_status(self) -> dict:
        return R.ok(dlc=self.dlc_status())

    def dlc_install(self) -> dict:
        """Blocks on the download; the lock is not held."""
        try:
            verified = dlc.install()
        except dlc.DlcError as exc:
            return R.error("dlc_failed", str(exc), dlc=self.dlc_status())
        except Exception as exc:
            return R.error("dlc_failed", "Could not install the DLC:\n\n" + net.describe_error(exc),
                           dlc=self.dlc_status())
        dlc.reload()
        return R.ok(verified=verified, dlc=self.dlc_status())

    def dlc_remove(self, confirm=None) -> dict:
        choice = answer(confirm, "remove_dlc")
        if choice is None:
            return R.needs_confirm(
                "remove_dlc", "Remove Image OCR",
                "Remove the Image OCR DLC?\n\nYour saved entries are not affected.",
                [opt("remove", "Remove", "danger"), opt("cancel", "Cancel", "neutral")],
                default="cancel", cancel="cancel", icon="warning")
        if choice != "remove":
            return R.cancelled(dlc=self.dlc_status())
        try:
            dlc.remove()
        except dlc.DlcError as exc:
            return R.error("dlc_failed", str(exc), dlc=self.dlc_status())
        dlc.reload()
        return R.ok(dlc=self.dlc_status())

    def remember_update(self, version: str, url: str, sha_url: str | None = None):
        """Called by the background check so install_update can use it."""
        self._update = (version, url, sha_url)

    @property
    def pending_update(self) -> tuple[str, str, str | None] | None:
        return self._update

    def check_updates(self, current_version: str) -> dict:
        """Manual check; network calls run without the lock."""
        import updater
        try:
            release = updater.fetch_latest_release()
        except Exception as exc:
            return R.error("network", "Could not check for updates:\n"
                                      + net.describe_error(exc))
        available = bool(release and updater._is_newer(release[0], current_version))
        if available:
            self.remember_update(*release)
        app = {"current": current_version, "latest": release[0] if release else None,
               "available": available}
        dlc_info = None
        st = dlc.load_status()
        if st["state"] == "ok":
            try:
                latest = updater.fetch_latest_dlc_version()
            except Exception:
                latest = None   # a DLC check failure must not mask the app result
            current = st["version"] or "0.0.0"
            newer = bool(latest and updater._is_newer(latest, current))
            if newer:
                self.dlc_update_version = latest
            dlc_info = {"current": st["version"], "latest": latest, "available": newer}
        message = None
        if not available:
            message = f"You're up to date (v{current_version})."
            if dlc_info and dlc_info["available"]:
                message += (f"\n\nA newer Image OCR DLC (v{dlc_info['latest']}) is "
                            "available — see the DLC Store below.")
        return R.ok(message, app=app, dlc=dlc_info)

    def install_update(self, frozen: bool | None = None, current: str = "") -> dict:
        """Download/verify/run the remembered installer (lock not held, bar
        the pre-update copy of the user's files, which must succeed first)."""
        import updater
        if frozen is None:
            frozen = bool(getattr(sys, "frozen", False))
        if not frozen:
            return R.error("not_frozen", "Updates can only be installed from the "
                                         "installed app, not when running from source.")
        if self._update is None:
            return R.error("update_failed", "No update has been found yet — "
                                            "check for updates first.")
        version, url, sha = self._update
        try:
            with self._lock:
                storage.pre_update_copy(current, version)
        except OSError as exc:
            return R.error("update_failed", "Your data couldn't be backed up, so the "
                                            f"update was not installed:\n\n{exc}")
        try:
            updater.apply_update(url, sha)
        except Exception as exc:
            return R.error("update_failed", "The update could not be installed:\n\n"
                                            + net.describe_error(exc))
        return R.ok(version=version)
