import json
import os
from datetime import datetime
from enum import Enum


_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Tyoaikaweleho")
_SESSION_FILE = os.path.join(_DATA_DIR, "session.json")


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

    def stop(self) -> dict | None:
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
        self._clear_session()
        return result

    def elapsed_str(self) -> str:
        if self.state != TimerState.RUNNING or self._start_dt is None:
            return "00:00"
        delta = datetime.now() - self._start_dt
        total = int(delta.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        return f"{h:02d}:{m:02d}"

    def elapsed_seconds(self) -> float:
        if self.state != TimerState.RUNNING or self._start_dt is None:
            return 0.0
        return (datetime.now() - self._start_dt).total_seconds()

    def start_time_str(self) -> str:
        if self._start_dt is None:
            return ""
        return self._start_dt.strftime("%H:%M")

    @property
    def is_running(self) -> bool:
        return self.state == TimerState.RUNNING

    # ── Session persistence ──────────────────────────────────────

    def _save_session(self):
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "job_shift": self._job_shift,
                "start": self._start_dt.isoformat(),
            }, f)

    def _clear_session(self):
        try:
            os.remove(_SESSION_FILE)
        except FileNotFoundError:
            pass


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


def clear_saved_session():
    try:
        os.remove(_SESSION_FILE)
    except FileNotFoundError:
        pass
