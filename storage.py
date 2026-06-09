import json
import os
import shutil
import uuid
from dataclasses import dataclass, asdict
from datetime import date, time


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
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_raw(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_month(year: int, month: int) -> list[WorkEntry]:
    data = _load_raw()
    prefix = f"{year:04d}-{month:02d}"
    return [WorkEntry(**e) for e in data["entries"] if e["date"].startswith(prefix)]


def load_all_entries() -> list[WorkEntry]:
    data = _load_raw()
    return [WorkEntry(**e) for e in data["entries"]]


def save_entry(entry: WorkEntry):
    data = _load_raw()
    data["entries"] = [e for e in data["entries"] if e["id"] != entry.id]
    data["entries"].append(asdict(entry))
    data["entries"].sort(key=lambda e: (e["date"], e["time_in"]))
    _save_raw(data)


def delete_entry(entry_id: str):
    data = _load_raw()
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    _save_raw(data)


def update_entry(entry: WorkEntry):
    save_entry(entry)


def get_pay_rate() -> float:
    return _load_raw().get("pay_rate", 20.0)


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
_DEFAULT_SHIFTS = ["GPSR", "Sales", "Sales/Support", "Support", "Training", "Onboarding"]


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
