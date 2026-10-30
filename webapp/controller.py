"""All v1.3 UI rules (timer panel, main window, entries table, edit dialog,
settings view) as plain methods returning result envelopes. No pywebview,
no dialogs: the api layer passes file paths in and shows the confirms.
See docs/V2_UI_API.md."""
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
                   is_long_shift, is_overnight, parse_date_input, parse_pay_rate,
                   parse_time_input, resolve_start_time, start_time_needs_confirm,
                   week_key)
from webapp import results as R
from webapp.results import Stale, answer, describe, entry_row, money, opt, work_entry_dict

MAX_ENTRY_MINUTES = 24 * 60
RECOVERY_LIMIT = timedelta(hours=8)


def _session_start(session: dict) -> datetime | None:
    try:
        start = datetime.fromisoformat(session["start"])
    except (TypeError, ValueError, KeyError):
        return None
    if start.tzinfo is not None:
        start = start.astimezone().replace(tzinfo=None)
    return start
MAX_STATS_DAYS = 3700

_LOCKED_HINT = "Close any program that may be locking data.json"


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


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

    # ── helpers ──────────────────────────────────────────────────

    def _now(self) -> datetime:
        return self._clock()

    def _session_pending(self) -> bool:
        return not self._timer.is_running and timer_module.load_saved_session() is not None

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
    def _long_entry_confirm(t_in: str, t_out: str, minutes: int) -> dict:
        overnight = is_overnight(t_in, t_out)
        return R.needs_confirm(
            "long_entry", "Long shift",
            f"{t_in}–{t_out} is {format_duration(minutes)}"
            f"{' (ending the next day)' if overnight else ''}.\n\nSave it anyway?",
            [opt("save", "Save anyway", "primary"), opt("cancel", "Cancel", "neutral")],
            default="save", cancel="cancel", icon="warning",
            details={"time_in": t_in, "time_out": t_out, "overnight": overnight,
                     "elapsed_minutes": minutes})

    # ── app / lifecycle ──────────────────────────────────────────

    def changelog(self, current_version: str) -> list[dict] | None:
        """Versions newer than the last one run, newest first (or None), and
        records *current_version* as seen."""
        import changelog as cl
        last = storage.get_last_seen_version()
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
            token = _iso(t.start_dt)
            try:
                choice = answer(confirm, "close_running", token)
            except Stale:
                return R.stale(timer=self.timer_state())
            if choice is None:
                minutes = int((self._now() - t.start_dt).total_seconds() // 60)
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
                    details={"start_iso": token, "elapsed_minutes": minutes})
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
            js = (job_shift or storage.get_default_job_shift() or "").strip() or "—"
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

    def _stop(self, source: str, confirm) -> dict:
        t = self._timer
        start, job_shift = t.start_dt, t.job_shift
        token = _iso(start)
        elapsed = (self._now() - start).total_seconds()
        minutes = max(0, int(elapsed // 60))
        details = {"start_iso": token, "elapsed_minutes": minutes}
        long = is_long_shift(minutes)

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
        if minutes >= MAX_ENTRY_MINUTES:
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

        entry = storage.WorkEntry(
            id=storage.new_entry_id(), date=start.strftime("%Y-%m-%d"),
            job_shift=job_shift, time_in=start.strftime("%H:%M"),
            time_out=time_out or self._now().strftime("%H:%M"))
        t.stop()
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
        return R.saved(entry=entry_row(entry), timer=self.timer_state())

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
                self._clear_session()
                return None
            now = self._now()
            over_limit = now - start >= RECOVERY_LIMIT
            suggested = start + RECOVERY_LIMIT if over_limit else now
            job_shift = session.get("job_shift")
            return {
                "start_iso": _iso(start), "start_epoch_ms": _epoch_ms(start),
                "job_shift": job_shift if isinstance(job_shift, str) else "?",
                "elapsed_minutes": max(0, int((now - start).total_seconds() // 60)),
                "over_limit": over_limit, "suggested_end": suggested.strftime("%H:%M"),
            }

    def recovery_resolve(self, action: str, end: str | None = None, confirm=None) -> dict:
        with self._lock:
            rec = self.recovery()
            if rec is None:
                return R.ok(timer=self.timer_state(), recovery=None)
            start = datetime.fromisoformat(rec["start_iso"])
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
                entry = storage.WorkEntry(
                    id=storage.new_entry_id(), date=start.strftime("%Y-%m-%d"),
                    job_shift=rec["job_shift"], time_in=start.strftime("%H:%M"),
                    time_out=t_out)
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
                               recovery=None)

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
        rows = [entry_row(e) for e in entries]
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
            job_shift=str(draft.get("job_shift") or "").strip(),
            time_in=t_in, time_out=t_out)
        with self._lock:
            try:
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
            entry = self._find(entry_id)
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
            try:
                storage.update_entry(entry)
            except OSError as exc:
                return R.error("save_failed",
                               f"The change could not be saved:\n\n{exc}\n\n"
                               "Close any program using data.json and try again.")
            return R.saved(entry=entry_row(entry))

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
            return R.ok(f"Deleted {desc}.", deleted=work_entry_dict(entry), description=desc)

    def restore_entry(self, entry: dict) -> dict:
        if not isinstance(entry, dict) or not all(
                isinstance(entry.get(k), str) for k in ("id", "date", "time_in")):
            return R.invalid("entry", "That is not a saved entry.")
        restored = storage.WorkEntry(**{
            k: str(entry.get(k) or "")
            for k in ("id", "date", "job_shift", "time_in", "time_out")})
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
        js = str(name or "").strip()
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

    # ── import / export / OCR ────────────────────────────────────

    @staticmethod
    def export_filename(year: int, month: int) -> str:
        return f"Hours {date(int(year), int(month), 1):%B %Y}.xlsx"

    def export_month(self, year: int, month: int, path: str | None) -> dict:
        if not path:
            return R.cancelled()
        import excel_export
        with self._lock:
            entries = storage.load_month(int(year), int(month))
            fmt = storage.get_export_format()
            include_pay = storage.get_export_include_pay()
            rate = storage.get_pay_rate()
        try:
            excel_export.export_month(entries=entries, year=int(year), month=int(month),
                                      save_path=path, fmt=fmt, include_pay=include_pay,
                                      pay_rate=rate)
        except PermissionError:
            return R.error("file_locked",
                           f"Could not write:\n{path}\n\n"
                           "The file is probably open in Excel — close it and try again.")
        except Exception as exc:
            return R.error("internal", f"Could not export:\n\n{exc}")
        return R.saved(f"Timesheet saved to:\n{path}", path=path)

    def import_excel(self, paths) -> dict:
        paths = [p for p in (paths or []) if p]
        if not paths:
            return R.cancelled()
        import import_excel
        imported = skipped = 0
        errors = []
        with self._lock:
            for path in paths:
                try:
                    imp, skp = import_excel.import_from_file(path)
                    imported += imp
                    skipped += skp
                except Exception as exc:
                    errors.append(f"{path}: {exc}")
        n = len(paths)
        msg = (f"Imported {imported} {_plural(imported, 'entry', 'entries')}"
               f" from {n} {_plural(n, 'file', 'files')}.")
        if skipped:
            msg += f"\n{skipped} {_plural(skipped, 'duplicate', 'duplicates')} skipped."
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors)
        return R.ok(msg, imported=imported, skipped=skipped, files=n, errors=errors)

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

    def install_update(self, frozen: bool | None = None) -> dict:
        """Download/verify/run the remembered installer (lock not held)."""
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
            updater.apply_update(url, sha)
        except Exception as exc:
            return R.error("update_failed", "The update could not be installed:\n\n"
                                            + net.describe_error(exc))
        return R.ok(version=version)
