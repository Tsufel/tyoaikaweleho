import json
import os
from datetime import datetime
from enum import Enum


# WELEHO_DATA_DIR (see storage.py) keeps dev/test sessions out of AppData
_DATA_DIR = (os.path.abspath(os.environ["WELEHO_DATA_DIR"].strip())
             if os.environ.get("WELEHO_DATA_DIR", "").strip()
             else os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Tyoaikaweleho"))
_SESSION_FILE = os.path.join(_DATA_DIR, "session.json")


def _epoch(dt: datetime) -> float:
    """Seconds since the epoch for a naive local time (its fold picks the
    first or second pass of a repeated DST hour)."""
    return dt.timestamp()


def elapsed_between(start: datetime, end: datetime) -> float:
    """Real seconds from *start* to *end*, both naive local times. Goes by
    the epoch, so the night the clocks go back (or forward) doesn't lose
    or add an hour the way plain wall-clock subtraction does."""
    try:
        return _epoch(end) - _epoch(start)
    except (OverflowError, OSError, ValueError):
        return (end - start).total_seconds()


class TimerState(Enum):
    IDLE = "idle"
    RUNNING = "running"


class WorkTimer:
    def __init__(self):
        self.state = TimerState.IDLE
        self._start_dt: datetime | None = None
        self._job_shift: str = "GPSR"

    def start(self, job_shift: str, start_time: datetime | None = None):
        if self.state == TimerState.RUNNING:
            return
        self._start_dt = start_time if start_time is not None else datetime.now()
        self._job_shift = job_shift
        self.state = TimerState.RUNNING
        self._save_session()

    def set_start(self, start_time: datetime, job_shift: str):
        """Change the running shift's start and job. If session.json can't be
        written the old values are kept and the OSError is raised."""
        if self.state != TimerState.RUNNING:
            return
        old = (self._start_dt, self._job_shift)
        self._start_dt, self._job_shift = start_time, job_shift
        try:
            self._save_session()
        except OSError:
            self._start_dt, self._job_shift = old
            raise

    def stop(self) -> dict | None:
        """Stop and return the finished shift. session.json is left in place
        so the shift can still be recovered if saving it fails — call
        clear_saved_session() once the entry is safely stored."""
        if self.state != TimerState.RUNNING:
            return None
        end_dt = datetime.now()
        result = {
            "date": self._start_dt.strftime("%Y-%m-%d"),
            "job_shift": self._job_shift,
            "time_in": self._start_dt.strftime("%H:%M"),
            "time_out": end_dt.strftime("%H:%M"),
        }
        self.state = TimerState.IDLE
        self._start_dt = None
        return result

    def elapsed_str(self) -> str:
        if self.state != TimerState.RUNNING or self._start_dt is None:
            return "00:00"
        total = max(0, int(elapsed_between(self._start_dt, datetime.now())))
        h = total // 3600
        m = (total % 3600) // 60
        return f"{h:02d}:{m:02d}"

    def elapsed_seconds(self) -> float:
        if self.state != TimerState.RUNNING or self._start_dt is None:
            return 0.0
        return elapsed_between(self._start_dt, datetime.now())

    @property
    def start_dt(self) -> datetime | None:
        return self._start_dt

    @property
    def job_shift(self) -> str:
        return self._job_shift

    def start_time_str(self) -> str:
        if self._start_dt is None:
            return ""
        return self._start_dt.strftime("%H:%M")

    @property
    def is_running(self) -> bool:
        return self.state == TimerState.RUNNING

    # ── Session persistence ──────────────────────────────────────

    def _save_session(self):
        # temp file + replace: a crash mid-write never leaves a half-written
        # session.json (which would lose the running shift)
        os.makedirs(_DATA_DIR, exist_ok=True)
        tmp = _SESSION_FILE + ".tmp"
        session = {"job_shift": self._job_shift, "start": self._start_dt.isoformat()}
        if self._start_dt.fold:
            # isoformat() drops the fold: without this a start in the second
            # pass of the repeated DST hour would come back an hour early
            session["start_fold"] = 1
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(session, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _SESSION_FILE)


def load_saved_session() -> dict | None:
    """Return saved session dict or None if no session file exists."""
    if not os.path.exists(_SESSION_FILE):
        return None
    try:
        with open(_SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        datetime.fromisoformat(data["start"])  # validate
        return data
    except Exception:
        return None


def mark_session_saved(entry_id: str):
    """Record in session.json the id of the entry the shift was saved as,
    just before saving it. If session.json then can't be removed, the next
    launch sees the entry exists and doesn't offer the shift again."""
    data = load_saved_session()
    if data is None:
        return
    data["saved_entry_id"] = entry_id
    tmp = _SESSION_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _SESSION_FILE)


def clear_saved_session():
    try:
        os.remove(_SESSION_FILE)
    except FileNotFoundError:
        pass
