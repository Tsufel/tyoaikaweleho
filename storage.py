import json
import math
import os
import re
import shutil
import sys
import unicodedata
import uuid
from dataclasses import dataclass, asdict
from datetime import date, datetime, time

from utils import parse_date_input, parse_time_input

# Dev / test / smoke runs point this at a scratch folder so they never touch
# the real data next to the exe (timer.py honours it for session.json too)
DATA_DIR_ENV = "WELEHO_DATA_DIR"
_DATA_DIR_OVERRIDE = os.environ.get(DATA_DIR_ENV, "").strip()

if _DATA_DIR_OVERRIDE:
    DATA_DIR = os.path.abspath(_DATA_DIR_OVERRIDE)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except OSError:
        pass
elif getattr(sys, "frozen", False):
    # Running as PyInstaller bundle — data lives next to the .exe
    DATA_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, "data.json")

# never migrate the real AppData copy into an overridden data dir
_APPDATA_FILE = "" if _DATA_DIR_OVERRIDE else os.path.join(
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
    if _APPDATA_FILE and os.path.exists(_APPDATA_FILE) and not os.path.exists(DATA_FILE):
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
# the form Tk's wm_geometry() reports ("+-1500" for a negative position)
_TK_GEOMETRY = re.compile(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")


def _legacy_geometry(saved) -> tuple[str, bool] | None:
    if not isinstance(saved, dict):
        return None
    geom = saved.get("geometry")
    if not isinstance(geom, str) or not _GEOMETRY.fullmatch(geom):
        return None
    return geom, bool(saved.get("zoomed", False))


def get_window_geometry() -> tuple[str, bool] | None:
    """(Tk geometry string of the restored window, was it maximised) from
    the last close, or None if never saved or unreadable."""
    return _legacy_geometry(_load_raw().get("window_geometry"))


def set_window_geometry(geom: str, zoomed: bool):
    data = _load_raw()
    data["window_geometry"] = {"geometry": geom, "zoomed": bool(zoomed)}
    _save_raw(data)


_PLACEMENT_VERSION = 2
_PLACEMENT_KEYS = ("left", "top", "right", "bottom")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _clean_placement(p) -> dict | None:
    if not isinstance(p, dict) or p.get("v") != _PLACEMENT_VERSION:
        return None
    if not all(_is_int(p.get(k)) for k in _PLACEMENT_KEYS):
        return None
    if p["right"] <= p["left"] or p["bottom"] <= p["top"]:
        return None
    return {"v": _PLACEMENT_VERSION,
            **{k: p[k] for k in _PLACEMENT_KEYS},
            "maximized": bool(p.get("maximized", False))}


def get_window_placement() -> dict | None:
    """Restored-window rectangle and maximised flag from the last close:
    {v: 2, left, top, right, bottom, maximized}. Falls back to the v1 Tk
    geometry ("WxH+X+Y"); None if neither is usable."""
    data = _load_raw()
    placement = _clean_placement(data.get("window_placement"))
    if placement is not None:
        return placement
    legacy = _legacy_geometry(data.get("window_geometry"))
    m = _TK_GEOMETRY.fullmatch(legacy[0]) if legacy else None
    if m is None:
        return None
    w, h, x, y = (int(g) for g in m.groups())
    if w <= 0 or h <= 0:
        return None
    return {"v": _PLACEMENT_VERSION, "left": x, "top": y, "right": x + w,
            "bottom": y + h, "maximized": legacy[1]}


def set_window_placement(placement: dict):
    """Store a placement (see get_window_placement). The v1 geometry key is
    written too, so a downgrade to v1.3 still restores the window."""
    clean = _clean_placement({**placement, "v": _PLACEMENT_VERSION}
                             if isinstance(placement, dict) else None)
    if clean is None:
        raise ValueError(f"invalid window placement: {placement!r}")
    w, h = clean["right"] - clean["left"], clean["bottom"] - clean["top"]
    data = _load_raw()
    data["window_placement"] = clean
    data["window_geometry"] = {"geometry": f"{w}x{h}+{clean['left']}+{clean['top']}",
                               "zoomed": clean["maximized"]}
    _save_raw(data)


UI_PREF_DEFAULTS = {"lulz": False, "reduce_effects": False, "lulz_sound": False,
                    "liquid_glass": False, "target_hours": 8.0, "pet": "off", "pet_name": ""}
_BOOL_PREFS = ("lulz", "reduce_effects", "lulz_sound", "liquid_glass")
TARGET_HOURS_RANGE = (1.0, 24.0)
PETS = ("off", "familiar", "wizard")
PET_NAME_MAX = 24


# Control, surrogate, private-use and line/paragraph separator characters, and
# the bidi overrides. Joiners (ZWJ in emoji, ZWNJ in Persian/Indic names) and
# variation selectors are fine.
_BAD_NAME_CATEGORIES = ("Cc", "Cs", "Co", "Zl", "Zp")
_BIDI_CONTROLS = {chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A))}


def _pet_name_error(v) -> str | None:
    """Why *v* can't be a pet name, or None when it can."""
    if not isinstance(v, str):
        return f"pet_name must be text of at most {PET_NAME_MAX} characters"
    if any(unicodedata.category(c) in _BAD_NAME_CATEGORIES or c in _BIDI_CONTROLS for c in v):
        return "pet_name has control characters"
    if len(" ".join(v.split())) > PET_NAME_MAX:
        return f"pet_name must be text of at most {PET_NAME_MAX} characters"
    return None


def _clean_pet_name(v) -> str | None:
    """Trimmed name, or None when *v* is not a usable one ("" = default name)."""
    if _pet_name_error(v):
        return None
    return " ".join(v.split())


def _valid_target_hours(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v)
            and TARGET_HOURS_RANGE[0] <= v <= TARGET_HOURS_RANGE[1])


def _clean_ui_prefs(raw) -> dict:
    prefs = dict(UI_PREF_DEFAULTS)
    if isinstance(raw, dict):
        for key in _BOOL_PREFS:
            if isinstance(raw.get(key), bool):
                prefs[key] = raw[key]
        if _valid_target_hours(raw.get("target_hours")):
            prefs["target_hours"] = float(raw["target_hours"])
        if raw.get("pet") in PETS:
            prefs["pet"] = raw["pet"]
        name = _clean_pet_name(raw.get("pet_name"))
        if name is not None:
            prefs["pet_name"] = name
    return prefs


def merge_ui_prefs(base, changes: dict) -> dict:
    """*base* (cleaned) with the keys in *changes* applied. Raises
    ValueError for an unknown key or a bad value."""
    if not isinstance(changes, dict):
        raise ValueError("ui_prefs must be an object")
    prefs = _clean_ui_prefs(base)
    for key, value in changes.items():
        if key in _BOOL_PREFS:
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false")
            prefs[key] = value
        elif key == "target_hours":
            if not _valid_target_hours(value):
                raise ValueError("target_hours must be between 1 and 24")
            prefs[key] = float(value)
        elif key == "pet":
            if value not in PETS:
                raise ValueError("pet must be off, familiar or wizard")
            prefs[key] = value
        elif key == "pet_name":
            problem = _pet_name_error(value)
            if problem:
                raise ValueError(problem)
            prefs[key] = " ".join(value.split())
        else:
            raise ValueError(f"unknown ui pref: {key}")
    return prefs


def get_ui_prefs() -> dict:
    """{lulz, reduce_effects, lulz_sound, liquid_glass, target_hours, pet, pet_name},
    defaults for anything unset."""
    return _clean_ui_prefs(_load_raw().get("ui_prefs"))


def set_ui_prefs(changes: dict) -> dict:
    """Apply a partial ui_prefs update; returns the stored prefs."""
    data = _load_raw()
    prefs = merge_ui_prefs(data.get("ui_prefs"), changes)
    data["ui_prefs"] = prefs
    _save_raw(data)
    return prefs


def _clean_achievements_seen(raw) -> dict:
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, str) and _ISO_DATE.fullmatch(v):
                out[k] = v
    return out


def get_achievements_seen() -> dict | None:
    """{achievement id: "YYYY-MM-DD" it was met}, or None if achievements have
    never been acknowledged (first run: everything already met is backfilled)."""
    raw = _load_raw().get("achievements_seen")
    return None if raw is None else _clean_achievements_seen(raw)


def add_achievements_seen(seen: dict) -> dict:
    """Merge *seen* into the stored set (earliest date wins) and return it.
    Always writes, so an empty dict ends the first run."""
    data = _load_raw()
    merged = _clean_achievements_seen(data.get("achievements_seen"))
    for k, v in _clean_achievements_seen(seen).items():
        merged[k] = min(v, merged.get(k, v))
    data["achievements_seen"] = merged
    _save_raw(data)
    return merged


EXPORT_FORMATS = ("Simple", "Full")


def _check_setting(key: str, value):
    if key == "pay_rate":
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError("pay_rate must be a positive number")
    elif key == "default_start_time":
        if not isinstance(value, str) or parse_time_input(value) != value:
            raise ValueError("default_start_time must be HH:MM")
    elif key == "default_job_shift":
        if not isinstance(value, str):
            raise ValueError("default_job_shift must be a string")
    elif key == "export_format":
        if value not in EXPORT_FORMATS:
            raise ValueError(f"export_format must be one of {EXPORT_FORMATS}")
    elif key == "export_include_pay":
        if not isinstance(value, bool):
            raise ValueError("export_include_pay must be true or false")
    elif key == "appearance_mode":
        if value not in APPEARANCE_MODES:
            raise ValueError(f"appearance mode must be one of {APPEARANCE_MODES}")
    elif key != "ui_prefs":
        raise ValueError(f"unknown setting: {key}")


def save_settings(values: dict):
    """Write several settings in one load/save, so either all or none of
    them are stored. Keys are the data.json names (pay_rate,
    default_start_time, default_job_shift, export_format,
    export_include_pay, appearance_mode, ui_prefs — which may be partial).
    Raises ValueError, writing nothing, for a bad key or value."""
    for key, value in values.items():
        _check_setting(key, value)
    data = _load_raw()
    for key, value in values.items():
        if key == "ui_prefs":
            value = merge_ui_prefs(data.get("ui_prefs"), value)
        elif key == "pay_rate":
            value = float(value)
        data[key] = value
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
