import json
import math
import os
import re
import shutil
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import date, datetime, time

from utils import parse_date_input


if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle — data lives next to the .exe
    DATA_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, "data.json")

_APPDATA_FILE = os.path.join(
    os.environ.get("APPDATA", ""), "Tyoaikaweleho", "data.json")


@dataclass
class WorkEntry:
    id: str
    date: str        # ISO format: "2025-06-02"
    job_shift: str
    time_in: str     # "HH:MM"
    time_out: str    # "HH:MM" or "" if still running


def _migrate_from_appdata():
    """Copy AppData data.json to local folder on first run."""
    if os.path.exists(_APPDATA_FILE) and not os.path.exists(DATA_FILE):
        shutil.copy2(_APPDATA_FILE, DATA_FILE)


def _load_raw() -> dict:
    _migrate_from_appdata()
    if not os.path.exists(DATA_FILE):
        return {"entries": [], "pay_rate": 20.0}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # data.json is corrupt (e.g. crash mid-write) — fall back to the
        # last known-good backup instead of crashing and losing everything
        backup = DATA_FILE + ".bak"
        if os.path.exists(backup):
            with open(backup, "r", encoding="utf-8") as f:
                return json.load(f)
        raise


def _save_raw(data: dict):
    # Atomic write: serialize to a temp file, back up the previous good
    # file, then swap the temp file into place. A crash at any point
    # leaves either the old file or the new file intact — never a
    # half-written data.json.
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    if os.path.exists(DATA_FILE):
        try:
            shutil.copy2(DATA_FILE, DATA_FILE + ".bak")
        except OSError:
            pass
        _daily_snapshot()
    os.replace(tmp, DATA_FILE)


_SNAPSHOT_KEEP = 14


def _daily_snapshot():
    """Keep one copy of data.json per day (as it was before the day's first
    save) in backups/, pruned to the newest _SNAPSHOT_KEEP. The .bak file
    only ever holds the state from one save ago."""
    try:
        backup_dir = os.path.join(os.path.dirname(DATA_FILE), "backups")
        target = os.path.join(backup_dir, f"data-{date.today().isoformat()}.json")
        if os.path.exists(target):
            return
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(DATA_FILE, target)
        snapshots = sorted(f for f in os.listdir(backup_dir)
                           if f.startswith("data-") and f.endswith(".json"))
        for old in snapshots[:-_SNAPSHOT_KEEP]:
            os.remove(os.path.join(backup_dir, old))
    except OSError:
        pass


_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _normalise_date(s: str) -> str:
    """ISO form of a stored date. Older versions could save loose input such
    as '20250602' verbatim, which hid the entry from every month view."""
    if _ISO_DATE.fullmatch(s):
        return s
    return parse_date_input(s) or s


def _entry(e: dict) -> WorkEntry:
    return WorkEntry(**{**e, "date": _normalise_date(e["date"])})


def load_month(year: int, month: int) -> list[WorkEntry]:
    data = _load_raw()
    prefix = f"{year:04d}-{month:02d}"
    entries = (_entry(e) for e in data["entries"])
    return [e for e in entries if e.date.startswith(prefix)]


def load_all_entries() -> list[WorkEntry]:
    data = _load_raw()
    return [_entry(e) for e in data["entries"]]


def save_entry(entry: WorkEntry):
    data = _load_raw()
    data["entries"] = [e for e in data["entries"] if e["id"] != entry.id]
    data["entries"].append(asdict(entry))
    for e in data["entries"]:
        e["date"] = _normalise_date(e["date"])
    data["entries"].sort(key=lambda e: (e["date"], e["time_in"]))
    _save_raw(data)


def delete_entry(entry_id: str):
    data = _load_raw()
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    _save_raw(data)


def update_entry(entry: WorkEntry):
    save_entry(entry)


_DEFAULT_PAY_RATE = 20.0


def get_pay_rate() -> float:
    rate = _load_raw().get("pay_rate", _DEFAULT_PAY_RATE)
    # bool is an int subclass; nan/inf got in through older Settings versions
    if (isinstance(rate, bool) or not isinstance(rate, (int, float))
            or not math.isfinite(rate) or rate <= 0):
        return _DEFAULT_PAY_RATE
    return float(rate)


def set_pay_rate(rate: float):
    data = _load_raw()
    data["pay_rate"] = rate
    _save_raw(data)


def get_default_start_time() -> str:
    return _load_raw().get("default_start_time", "09:30")


def set_default_start_time(t: str):
    data = _load_raw()
    data["default_start_time"] = t
    _save_raw(data)


def new_entry_id() -> str:
    return str(uuid.uuid4())


SHIFTS_FILE = os.path.join(DATA_DIR, "shifts.txt")
_DEFAULT_SHIFTS = ["Sales", "Support", "Warehouse", "Sales/Support", "Training", "Onboarding"]


def _ensure_shifts_file():
    """Create shifts.txt with defaults if it doesn't exist."""
    if not os.path.exists(SHIFTS_FILE):
        with open(SHIFTS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(_DEFAULT_SHIFTS) + "\n")


def get_job_shift_list() -> list[str]:
    """Load shift list from shifts.txt (created with defaults if missing).
    Also appends any previously-used shifts not already in the file."""
    _ensure_shifts_file()
    with open(SHIFTS_FILE, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    data = _load_raw()
    for e in data["entries"]:
        js = e.get("job_shift", "").strip()
        if js and js not in lines:
            lines.append(js)
    return lines


def get_job_shift_history() -> list[str]:
    """Alias for get_job_shift_list() — kept for backward compat."""
    return get_job_shift_list()


def add_job_shift(js: str) -> bool:
    """Append *js* to shifts.txt. Returns True if added, False if already present."""
    _ensure_shifts_file()
    with open(SHIFTS_FILE, "r", encoding="utf-8") as f:
        existing = [ln.strip() for ln in f if ln.strip()]
    if any(e.lower() == js.lower() for e in existing):
        return False
    with open(SHIFTS_FILE, "a", encoding="utf-8") as f:
        f.write(js + "\n")
    return True


def get_default_job_shift() -> str:
    return _load_raw().get("default_job_shift", "GPSR")


def set_default_job_shift(js: str):
    data = _load_raw()
    data["default_job_shift"] = js
    _save_raw(data)


def get_export_format() -> str:
    """Return saved export format: 'Simple' or 'Full'. Default: 'Simple'."""
    return _load_raw().get("export_format", "Simple")


def set_export_format(fmt: str):
    data = _load_raw()
    data["export_format"] = fmt
    _save_raw(data)


def get_export_include_pay() -> bool:
    return bool(_load_raw().get("export_include_pay", False))


def set_export_include_pay(val: bool):
    data = _load_raw()
    data["export_include_pay"] = val
    _save_raw(data)


def get_last_seen_version() -> str | None:
    """Return the version string from the last time the app ran, or None on first install."""
    return _load_raw().get("last_seen_version")


def set_last_seen_version(v: str):
    data = _load_raw()
    data["last_seen_version"] = v
    _save_raw(data)


APPEARANCE_MODES = ("System", "Light", "Dark")


def get_appearance_mode() -> str:
    """'System', 'Light' or 'Dark'. Default: 'System' (follow Windows)."""
    mode = _load_raw().get("appearance_mode", "System")
    return mode if mode in APPEARANCE_MODES else "System"


def set_appearance_mode(mode: str):
    if mode not in APPEARANCE_MODES:
        raise ValueError(f"appearance mode must be one of {APPEARANCE_MODES}")
    data = _load_raw()
    data["appearance_mode"] = mode
    _save_raw(data)


_GEOMETRY = re.compile(r"\d+x\d+[+-]-?\d+[+-]-?\d+")


def get_window_geometry() -> tuple[str, bool] | None:
    """(Tk geometry string of the restored window, was it maximised) from
    the last close, or None if never saved or unreadable."""
    saved = _load_raw().get("window_geometry")
    if not isinstance(saved, dict):
        return None
    geom = saved.get("geometry")
    if not isinstance(geom, str) or not _GEOMETRY.fullmatch(geom):
        return None
    return geom, bool(saved.get("zoomed", False))


def set_window_geometry(geom: str, zoomed: bool):
    data = _load_raw()
    data["window_geometry"] = {"geometry": geom, "zoomed": bool(zoomed)}
    _save_raw(data)


ERROR_LOG = os.path.join(DATA_DIR, "error.log")
_ERROR_LOG_MAX = 256 * 1024


def append_error_log(text: str):
    """Append a timestamped traceback to error.log next to data.json (the
    exe has no console). Once over _ERROR_LOG_MAX, the older half is
    dropped. Never raises."""
    try:
        if os.path.exists(ERROR_LOG) and os.path.getsize(ERROR_LOG) > _ERROR_LOG_MAX:
            with open(ERROR_LOG, "r", encoding="utf-8", errors="replace") as f:
                kept = f.read()[-_ERROR_LOG_MAX // 2:]
            with open(ERROR_LOG, "w", encoding="utf-8") as f:
                f.write(kept)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now().isoformat(timespec='seconds')}\n{text.rstrip()}\n")
    except OSError:
        pass
