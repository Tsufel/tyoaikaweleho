import contextlib
import json
import math
import os
import re
import shutil
import sys
import threading
import time as _time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

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
    # Optional one-line note. Stored only when not blank, so a plain entry
    # keeps the five-key 2.1 shape and older versions carry it as an extra.
    note: str = ""
    # Keys this version doesn't know (written by a newer one, e.g. a break).
    # Carried through load, save and undo so going back a version never
    # strips them; never shown or compared.
    extra: dict = field(default_factory=dict, compare=False, repr=False)

    def to_dict(self) -> dict:
        """The stored form: the known fields win over any extra of the same name."""
        out = {**self.extra, **{k: getattr(self, k) for k in ENTRY_FIELDS}}
        if self.note:
            out["note"] = self.note
        return out

    @classmethod
    def from_dict(cls, e: dict) -> "WorkEntry":
        """Tolerant reader: unknown keys go to `extra`, missing text fields
        are blank (only id and date are required). A note that isn't text
        (some newer shape) stays in `extra` untouched."""
        known = {k: e.get(k, "") for k in ENTRY_FIELDS}
        known = {k: "" if v is None else v for k, v in known.items()}
        note = e.get("note")
        note = note if isinstance(note, str) else ""
        extra = {k: v for k, v in e.items()
                 if k not in ENTRY_FIELDS and not (k == "note" and isinstance(v, str))}
        return cls(**known, note=note, extra=extra)


ENTRY_FIELDS = ("id", "date", "job_shift", "time_in", "time_out")
NOTE_MAX = 200


def _migrate_from_appdata():
    """Copy AppData data.json to local folder on first run."""
    if _APPDATA_FILE and os.path.exists(_APPDATA_FILE) and not os.path.exists(DATA_FILE):
        shutil.copy2(_APPDATA_FILE, DATA_FILE)


class DataFileCorrupt(ValueError):
    """data.json can't be read and no backup could stand in for it."""


# Set when _load_raw had to stand in a backup for a damaged or missing
# data.json: {"source": <file used>, "damaged_copy": <where the damaged file
# was kept, "" if none>, "reason": "damaged" | "missing"}.
# Read once by the controller's bootstrap to tell the user.
last_recovery: dict | None = None

# How many times data.json has been read and parsed (for tests and profiling)
load_count = 0


def _parse_data(raw: bytes) -> dict | None:
    """data.json's content as a dict, or None if it isn't a JSON object."""
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_data_file(path: str) -> dict | None:
    try:
        with open(path, "rb") as f:
            return _parse_data(f.read())
    except OSError:
        return None


def _backup_candidates() -> list[str]:
    """Where a damaged data.json can be restored from, best first: the copy
    from one save ago, then the daily snapshots, newest first."""
    out = [DATA_FILE + ".bak"]
    backup_dir = os.path.join(os.path.dirname(DATA_FILE), "backups")
    try:
        snaps = sorted((f for f in os.listdir(backup_dir)
                        if _DAILY_SNAPSHOT.fullmatch(f)), reverse=True)
    except OSError:
        snaps = []
    out += [os.path.join(backup_dir, f) for f in snaps]
    return out


def _keep_damaged(raw: bytes) -> str:
    """Keep the damaged bytes next to data.json (one copy per distinct
    content, so repeated reads don't pile up copies). Returns its path, or
    "" if it couldn't be written."""
    import hashlib
    path = os.path.join(os.path.dirname(DATA_FILE),
                        f"data.damaged-{hashlib.sha1(raw).hexdigest()[:10]}.json")
    try:
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(raw)
        return path
    except OSError:
        return ""


def _restore_from_backup(reason: str, damaged: str = "") -> dict | None:
    """Stand in the newest backup that reads for data.json and write it
    back, so the next save doesn't back up a bad (or empty) file over a
    good one. None when no backup reads."""
    global last_recovery
    for path in _backup_candidates():
        data = _read_data_file(path)
        if data is None:
            continue
        note = (f" (damaged copy: {damaged or 'could not be kept'})"
                if reason == "damaged" else "")
        append_error_log(f"data.json was {reason}; restored from {path}{note}")
        try:
            _save_raw(data)
        except OSError as exc:
            append_error_log(f"could not write the restored data.json: {exc}")
        last_recovery = {"source": path, "damaged_copy": damaged, "reason": reason}
        return data
    return None


def _recover(raw: bytes) -> dict:
    """data.json is damaged (a crash mid-write, a disk error): keep a copy
    and stand in the newest backup that reads."""
    damaged = _keep_damaged(raw)
    data = _restore_from_backup("damaged", damaged)
    if data is not None:
        return data
    append_error_log(f"data.json is damaged and no backup could be read"
                     f" (damaged copy: {damaged or 'could not be kept'})")
    raise DataFileCorrupt(
        "Your hours file (data.json) is damaged and no backup of it could be "
        "read.\n\n"
        f"The damaged file was kept as {damaged or DATA_FILE}. "
        f"Backups are in {os.path.join(DATA_DIR, 'backups')}.")


def _load_raw() -> dict:
    """data.json freshly read and parsed: the caller may change and save it."""
    global load_count
    _migrate_from_appdata()
    if not os.path.exists(DATA_FILE):
        # Gone while backups remain (deleted by hand, a sync client, a bad
        # copy of the folder): starting empty would make the first save's
        # snapshot an empty file and push the good ones out of rotation.
        data = _restore_from_backup("missing")
        return data if data is not None else {"entries": [], "pay_rate": 20.0}
    load_count += 1
    with open(DATA_FILE, "rb") as f:   # a locked file raises OSError: not damage
        raw = f.read()
    data = _parse_data(raw)
    return data if data is not None else _recover(raw)


# ── per-call read cache ──────────────────────────────────────────────────────
# One API call can ask for the entries, the pay rate, the prefs... and each
# used to read and parse data.json again. Inside read_cache() the getters
# share one parsed copy instead. It is only trusted while data.json's
# (mtime, size, file id) are unchanged and no save has happened since (every
# _save_raw bumps _write_gen), so a change from this process or another one
# is picked up on the next read. Scopes are per thread: pywebview runs each
# API call on its own thread. Outside a scope nothing is cached.

_cache_local = threading.local()
_write_gen = 0


@contextlib.contextmanager
def read_cache():
    """Share one parsed data.json between the reads in this block (one API
    call). Nests; the cache is dropped when the outermost block ends."""
    depth = getattr(_cache_local, "depth", 0)
    _cache_local.depth = depth + 1
    try:
        yield
    finally:
        _cache_local.depth = depth
        if depth == 0:
            _cache_local.entry = None


def _file_key() -> tuple | None:
    try:
        st = os.stat(DATA_FILE)
    except OSError:
        return None
    return (DATA_FILE, st.st_mtime_ns, st.st_size, st.st_ino)


def _read_raw() -> dict:
    """data.json for reading only: never change or save the result (use
    _load_raw for that). Inside read_cache() it is parsed once per version
    of the file."""
    if not getattr(_cache_local, "depth", 0):
        return _load_raw()
    # key and generation are taken before reading: a change that lands
    # while we read leaves the cached copy already stale, never wrongly fresh
    key, gen = _file_key(), _write_gen
    cached = getattr(_cache_local, "entry", None)
    if key is not None and cached is not None and cached[0] == key and cached[1] == gen:
        return cached[2]
    data = _load_raw()
    _cache_local.entry = (key, gen, data) if key is not None else None
    return data


def _encode(data: dict) -> bytes:
    """data.json's bytes, as text mode wrote them before (os.linesep line
    ends). Raises (UnicodeEncodeError for a lone surrogate) before anything
    touches the disk."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    return text.replace("\n", os.linesep).encode("utf-8")


# Antivirus, the Search indexer or OneDrive can hold data.json for a moment,
# which makes os.replace fail with PermissionError on Windows
_REPLACE_TRIES = 5
_REPLACE_WAIT = 0.05


def _replace(src: str, dst: str):
    for attempt in range(_REPLACE_TRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_TRIES - 1:
                raise
            _time.sleep(_REPLACE_WAIT * (attempt + 1))


def _save_raw(data: dict):
    global _write_gen
    _write_gen += 1   # whatever happens below, cached reads are stale now
    # Atomic write: serialize to a temp file, back up the previous good
    # file, then swap the temp file into place. A crash at any point
    # leaves either the old file or the new file intact — never a
    # half-written data.json.
    blob = _encode(data)
    try:
        with open(DATA_FILE, "rb") as f:
            current = f.read()
    except OSError:   # missing, or locked (the replace below reports that)
        current = None
    if current == blob:
        # nothing changed: rewriting would turn .bak into a copy of this
        # file and lose the state from one real save ago
        return
    tmp = DATA_FILE + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        # only a file that reads is worth backing up: copying a damaged one
        # would replace the last good .bak / snapshot with it
        if current is not None and _parse_data(current) is not None:
            try:
                shutil.copy2(DATA_FILE, DATA_FILE + ".bak")
            except OSError:
                pass
            _daily_snapshot()
        _replace(tmp, DATA_FILE)
    except BaseException:
        try:   # never leave a half-written temp file behind
            os.remove(tmp)
        except OSError:
            pass
        raise


# Daily snapshots are kept grandfather-father-son style: the newest
# _SNAPSHOT_KEEP days, plus the newest of each of the _SNAPSHOT_WEEKS newest
# ISO weeks and of the _SNAPSHOT_MONTHS newest months that have one, so a
# mistake noticed weeks later still has a copy from before it.
_SNAPSHOT_KEEP = 14
_SNAPSHOT_WEEKS = 8
_SNAPSHOT_MONTHS = 12
# Only exactly this name is a daily snapshot: pruning and recovery never
# touch anything else in backups/ (a copy made in Explorer, a manual or
# pre-import/-restore/-update copy).
_DAILY_SNAPSHOT = re.compile(r"data-(\d{4}-\d{2}-\d{2})\.json")


def _snapshots_to_keep(days) -> set:
    days = sorted(set(days), reverse=True)
    keep = set(days[:_SNAPSHOT_KEEP])
    weeks: dict = {}
    months: dict = {}
    for d in days:   # newest first: the first one seen is its period's newest
        weeks.setdefault(d.isocalendar()[:2], d)
        months.setdefault((d.year, d.month), d)
    keep.update(sorted(weeks.values(), reverse=True)[:_SNAPSHOT_WEEKS])
    keep.update(sorted(months.values(), reverse=True)[:_SNAPSHOT_MONTHS])
    return keep


def _prune_snapshots(backup_dir: str):
    """Delete the daily snapshots _snapshots_to_keep doesn't keep. A name
    that doesn't parse as a date is left alone."""
    dated = {}
    for f in os.listdir(backup_dir):
        m = _DAILY_SNAPSHOT.fullmatch(f)
        if not m:
            continue
        try:
            dated[f] = date.fromisoformat(m.group(1))
        except ValueError:
            continue
    keep = _snapshots_to_keep(dated.values())
    for f, d in dated.items():
        if d not in keep:
            os.remove(os.path.join(backup_dir, f))


def _daily_snapshot():
    """Keep one copy of data.json per day (as it was before the day's first
    save) in backups/, pruned by _prune_snapshots. The .bak file only ever
    holds the state from one save ago."""
    try:
        backup_dir = os.path.join(os.path.dirname(DATA_FILE), "backups")
        target = os.path.join(backup_dir, f"data-{date.today().isoformat()}.json")
        if os.path.exists(target):
            return
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(DATA_FILE, target)
        _prune_snapshots(backup_dir)
    except OSError:
        pass


_PRE_IMPORT_KEEP = 5


def pre_import_snapshot() -> str:
    """Copy data.json to backups/pre-import-<timestamp>.json before a bulk
    import, keeping the newest _PRE_IMPORT_KEEP. The name must not start
    with "data-": those are the daily snapshots that pruning and recovery
    key on. Returns the copy's path ("" when there is no data.json yet).
    Raises OSError so the caller can refuse to import without a copy."""
    if not os.path.exists(DATA_FILE):
        return ""
    backup_dir = os.path.join(os.path.dirname(DATA_FILE), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(backup_dir, f"pre-import-{stamp}.json")
    if not os.path.exists(target):   # same second: keep the older state
        shutil.copy2(DATA_FILE, target)
    try:
        copies = sorted(f for f in os.listdir(backup_dir)
                        if f.startswith("pre-import-") and f.endswith(".json"))
        for old in copies[:-_PRE_IMPORT_KEEP]:
            os.remove(os.path.join(backup_dir, old))
    except OSError:
        pass
    return target


_PRE_UPDATE_KEEP = 3


def pre_update_copy(current: str, new: str) -> str:
    """Copy data.json, shifts.txt and session.json to
    backups/pre-update-v<current>-to-v<new>/ before an installer runs over
    the folder they live in, keeping the newest _PRE_UPDATE_KEEP such
    folders. Raises OSError: the update must not run without the copy."""
    def tag(v):
        return re.sub(r"[^0-9A-Za-z.+-]", "_", str(v or "unknown"))
    data_dir = os.path.dirname(DATA_FILE)
    backup_dir = os.path.join(data_dir, "backups")
    target = os.path.join(backup_dir, f"pre-update-v{tag(current)}-to-v{tag(new)}")
    os.makedirs(target, exist_ok=True)
    for src in (DATA_FILE, SHIFTS_FILE, os.path.join(data_dir, "session.json")):
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(target, os.path.basename(src)))
    os.utime(target)   # a retried update counts as the newest copy
    try:
        folders = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
                   if f.startswith("pre-update-")]
        folders = [f for f in folders if os.path.isdir(f)]
        folders.sort(key=os.path.getmtime)
        for old in folders[:-_PRE_UPDATE_KEEP]:
            if os.path.normcase(old) != os.path.normcase(target):
                shutil.rmtree(old, ignore_errors=True)
    except OSError:
        pass
    return target


# ── backups the user can see and restore (Settings → Your data) ──────────────
# Every kind below is a copy this app made. Anything else in backups/ (a copy
# made by hand) is neither listed, restored from, nor pruned.

_BACKUP_KINDS = (   # (kind, file-name pattern inside backups/)
    ("daily", _DAILY_SNAPSHOT),
    ("manual", re.compile(r"manual-\d{8}-\d{6}(?:-\d+)?\.json")),
    ("pre-import", re.compile(r"pre-import-\d{8}-\d{6}\.json")),
    ("pre-restore", re.compile(r"pre-restore-\d{8}-\d{6}(?:-\d+)?\.json")),
)
_PRE_UPDATE_DIR = re.compile(r"pre-update-v[0-9A-Za-z.+_-]+-to-v[0-9A-Za-z.+_-]+")
# path -> ((mtime_ns, size), summary): a listing doesn't re-parse old copies
_backup_summaries: dict = {}


def backups_dir() -> str:
    return os.path.join(os.path.dirname(DATA_FILE), "backups")


def _backup_files() -> list[tuple[str, str, str]]:
    """(name, kind, path) for every backup this app made. *name* is the
    only handle the UI gets: restore looks it up here again, so no path from
    outside is ever opened."""
    out = []
    bak = DATA_FILE + ".bak"
    if os.path.isfile(bak):
        out.append(("data.json.bak", "bak", bak))
    folder = backups_dir()
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    for f in names:
        path = os.path.join(folder, f)
        kind = next((k for k, rx in _BACKUP_KINDS if rx.fullmatch(f)), None)
        if kind and os.path.isfile(path):
            out.append((f, kind, path))
        elif _PRE_UPDATE_DIR.fullmatch(f) and os.path.isfile(os.path.join(path, "data.json")):
            out.append((f"{f}/data.json", "pre-update", os.path.join(path, "data.json")))
    return out


def _check_backup(data) -> bool:
    """A copy is restorable when it reads as this app's data: a JSON object
    whose entries (if any) are a list the normal loader can read."""
    if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
        return False
    try:
        _entries(data)
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _summarise(path: str) -> dict:
    st = os.stat(path)
    key = (st.st_mtime_ns, st.st_size)
    hit = _backup_summaries.get(path)
    if hit and hit[0] == key:
        return dict(hit[1])
    data = _read_data_file(path)
    ok = _check_backup(data)
    entries = _entries(data) if ok else []
    summary = {
        "ok": ok,
        "entries": len(entries) if ok else None,
        "last_entry_date": max((e.date for e in entries), default=None),
        "size": st.st_size,
        "saved_at": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }
    _backup_summaries[path] = (key, summary)
    return dict(summary)


def list_backups() -> list[dict]:
    """Every backup this app made, newest first: {name, kind, saved_at (when
    that data was last saved), size, ok, entries, last_entry_date}. Read-only."""
    out = []
    for name, kind, path in _backup_files():
        try:
            out.append({"name": name, "kind": kind, **_summarise(path)})
        except OSError:
            continue   # vanished or locked mid-listing
    out.sort(key=lambda b: (b["saved_at"], b["name"]), reverse=True)
    return out


def _stamped_copy(prefix: str) -> str:
    """Copy data.json to backups/<prefix>-<timestamp>.json, never over an
    existing file. Raises OSError."""
    folder = backups_dir()
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(folder, f"{prefix}-{stamp}.json")
    n = 2
    while os.path.exists(target):
        target = os.path.join(folder, f"{prefix}-{stamp}-{n}.json")
        n += 1
    shutil.copy2(DATA_FILE, target)
    return target


def manual_backup() -> str:
    """'Back up now': copy data.json to backups/manual-<timestamp>.json.
    Never pruned. Returns the copy's path ("" when there is no data.json yet).
    Raises OSError."""
    if not os.path.exists(DATA_FILE):
        return ""
    return _stamped_copy("manual")


def read_backup(name: str) -> dict | None:
    """The data in the listed backup *name*, or None when there is no such
    backup or it doesn't read as app data."""
    path = next((p for n, _k, p in _backup_files() if n == name), None)
    data = _read_data_file(path) if path else None
    return data if _check_backup(data) else None


def restore_backup(name: str) -> str:
    """Replace data.json with the listed backup *name*. The current
    data.json is copied to backups/pre-restore-<timestamp>.json first (never
    pruned); if that copy fails nothing is replaced. Returns the copy's path
    ("" when there was no data.json). Raises LookupError for an unknown or
    unreadable backup, OSError when a write fails."""
    data = read_backup(name)
    if data is None:
        raise LookupError(name)
    safety = _stamped_copy("pre-restore") if os.path.exists(DATA_FILE) else ""
    _save_raw(data)
    return safety


_ISO_DATE =re.compile(r"\d{4}-\d{2}-\d{2}")


def _normalise_date(s: str) -> str:
    """ISO form of a stored date. Older versions could save loose input such
    as '20250602' verbatim, which hid the entry from every month view."""
    if _ISO_DATE.fullmatch(s):
        return s
    return parse_date_input(s) or s


def _is_entry(e) -> bool:
    """A row this version can show. Rows a newer version may write that
    aren't shifts (a sync tombstone, `{"id", "deleted": true, ...}`) or that
    lack an id or date are skipped, but left untouched on disk."""
    return (isinstance(e, dict) and e.get("deleted") is not True
            and isinstance(e.get("id"), str) and isinstance(e.get("date"), str))


def _entry(e: dict) -> WorkEntry:
    entry = WorkEntry.from_dict(e)
    entry.date = _normalise_date(entry.date)
    return entry


def _entries(data: dict) -> list[WorkEntry]:
    return [_entry(e) for e in data.get("entries", []) if _is_entry(e)]


def load_month(year: int, month: int) -> list[WorkEntry]:
    prefix = f"{year:04d}-{month:02d}"
    return [e for e in _entries(_read_raw()) if e.date.startswith(prefix)]


def load_all_entries() -> list[WorkEntry]:
    return _entries(_read_raw())


def _sort_key(e) -> tuple:
    if not isinstance(e, dict):
        return ("", "")
    return (str(e.get("date") or ""), str(e.get("time_in") or ""))


def save_entry(entry: WorkEntry):
    add_entries([entry])


def add_entries(entries: list[WorkEntry]):
    """Add or replace entries by id with a single save, so a bulk import
    rotates .bak once and is all-or-nothing on disk."""
    if not entries:
        return
    ids = {e.id for e in entries}
    data = _load_raw()
    rows = [e for e in data.get("entries", [])
            if not (isinstance(e, dict) and e.get("id") in ids)]
    rows.extend(e.to_dict() for e in entries)
    for e in rows:
        if _is_entry(e):  # rows load skips (tombstones, bad rows) stay as they are
            e["date"] = _normalise_date(e["date"])
    rows.sort(key=_sort_key)
    data["entries"] = rows
    _save_raw(data)


def delete_entry(entry_id: str):
    data = _load_raw()
    data["entries"] = [e for e in data.get("entries", [])
                       if not (isinstance(e, dict) and e.get("id") == entry_id)]
    _save_raw(data)


def update_entry(entry: WorkEntry):
    save_entry(entry)


_DEFAULT_PAY_RATE = 20.0


def get_pay_rate() -> float:
    rate = _read_raw().get("pay_rate", _DEFAULT_PAY_RATE)
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
    return _read_raw().get("default_start_time", "09:30")


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


def _read_shifts_text() -> str:
    """shifts.txt as text. Notepad may have saved it as ANSI or with a BOM;
    both read. latin-1 decodes any byte, so this never raises for content."""
    with open(SHIFTS_FILE, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def _shift_lines(text: str) -> list[str]:
    lines = (ln.replace("﻿", "").strip() for ln in text.splitlines())
    return [ln for ln in lines if ln]


def get_job_shift_list() -> list[str]:
    """Load shift list from shifts.txt (created with defaults if missing).
    Also appends any previously-used shifts not already in the file. Names
    are de-duplicated ignoring case; the first spelling (the file's) wins."""
    _ensure_shifts_file()
    lines: list[str] = []
    seen: set[str] = set()
    used = (e.job_shift.strip() if isinstance(e.job_shift, str) else ""
            for e in _entries(_read_raw()))
    for js in (*_shift_lines(_read_shifts_text()), *used):
        if js and js.casefold() not in seen:
            seen.add(js.casefold())
            lines.append(js)
    return lines


def get_job_shift_history() -> list[str]:
    """Alias for get_job_shift_list() — kept for backward compat."""
    return get_job_shift_list()


def add_job_shift(js: str) -> bool:
    """Append *js* to shifts.txt. Returns True if added, False if already present.

    The file is rewritten whole through a temp file (as UTF-8, keeping every
    line and its line ends), so a last line Notepad saved without a newline
    doesn't get the new name glued on, and an ANSI file doesn't end up half
    ANSI, half UTF-8."""
    _ensure_shifts_file()
    text = _read_shifts_text()
    if any(e.casefold() == js.casefold() for e in _shift_lines(text)):
        return False
    newline = "\r\n" if "\r\n" in text else ("\n" if "\n" in text else os.linesep)
    if text and not text.endswith(("\n", "\r")):
        text += newline
    tmp = SHIFTS_FILE + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write((text + js + newline).encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, SHIFTS_FILE)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return True


def get_default_job_shift() -> str:
    """The shift chosen in Settings ("" = none chosen on purpose). Never set:
    the first shift in the list. Older versions fell back to a hard-coded
    "GPSR" even when it wasn't a shift; that stays only for people who have
    it in their list (in shifts.txt or used in an entry)."""
    stored = _read_raw().get("default_job_shift")
    if isinstance(stored, str):
        return stored
    try:
        shifts = get_job_shift_list()
    except (OSError, ValueError):  # shifts.txt unreadable: the defaults plus shifts in use
        shifts = list(_DEFAULT_SHIFTS) + [e.job_shift for e in _entries(_read_raw())]
    if _LEGACY_DEFAULT_SHIFT in shifts:
        return _LEGACY_DEFAULT_SHIFT
    return shifts[0] if shifts else ""


_LEGACY_DEFAULT_SHIFT = "GPSR"


def set_default_job_shift(js: str):
    data = _load_raw()
    data["default_job_shift"] = js
    _save_raw(data)


def get_export_format() -> str:
    """Return saved export format: 'Simple' or 'Full'. Default: 'Simple'."""
    return _read_raw().get("export_format", "Simple")


def set_export_format(fmt: str):
    data = _load_raw()
    data["export_format"] = fmt
    _save_raw(data)


def get_export_include_pay() -> bool:
    return bool(_read_raw().get("export_include_pay", False))


def set_export_include_pay(val: bool):
    data = _load_raw()
    data["export_include_pay"] = val
    _save_raw(data)


def get_last_seen_version() -> str | None:
    """Return the version string from the last time the app ran, or None on first install."""
    return _read_raw().get("last_seen_version")


def set_last_seen_version(v: str):
    data = _load_raw()
    data["last_seen_version"] = v
    _save_raw(data)


APPEARANCE_MODES = ("System", "Light", "Dark")


def get_appearance_mode() -> str:
    """'System', 'Light' or 'Dark'. Default: 'System' (follow Windows)."""
    mode = _read_raw().get("appearance_mode", "System")
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
    return _legacy_geometry(_read_raw().get("window_geometry"))


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
    data = _read_raw()
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
                    "liquid_glass": False, "target_hours": 8.0, "pet": "off", "pet_name": "",
                    "pet_hint_seen": False, "pet_skin": "classic"}
_BOOL_PREFS = ("lulz", "reduce_effects", "lulz_sound", "liquid_glass", "pet_hint_seen")
TARGET_HOURS_RANGE = (1.0, 24.0)
PETS = ("off", "familiar", "wizard")
PET_NAME_MAX = 24
# Pet looks (frontend/src/views/pet/petSkins.ts). Each unlocks at a pet level;
# the app shows a locked choice as classic, so only the id is checked here.
PET_SKINS = ("classic", "cosmic", "neon", "gilded", "legend")


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


JOB_SHIFT_MAX = 100


def clean_job_shift(v) -> str:
    """A job/shift name as typed, trimmed with inner runs of spaces made one.
    Raises ValueError (worded for the user) for non-text, a line break, tab
    or other control character (a newline would split shifts.txt), or a name
    over JOB_SHIFT_MAX characters. None is ""."""
    if v is None:
        return ""
    if not isinstance(v, str):
        raise ValueError("The shift name must be text.")
    if any(unicodedata.category(c) in _BAD_NAME_CATEGORIES or c in _BIDI_CONTROLS for c in v):
        raise ValueError("Shift names can't contain line breaks, tabs or other "
                         "control characters.")
    name = " ".join(v.split())
    if len(name) > JOB_SHIFT_MAX:
        raise ValueError(f"Shift names can be at most {JOB_SHIFT_MAX} characters.")
    return name


def clean_note(v) -> str:
    """A shift note as typed: one line, trimmed, inner whitespace (line
    breaks and tabs included) made single spaces. None is "". Raises
    ValueError (worded for the user) for non-text, other control characters
    or a note over NOTE_MAX characters."""
    if v is None:
        return ""
    if not isinstance(v, str):
        raise ValueError("The note must be text.")
    note = " ".join(v.split())
    if any(unicodedata.category(c) in _BAD_NAME_CATEGORIES or c in _BIDI_CONTROLS
           for c in note):
        raise ValueError("Notes can't contain control characters.")
    if len(note) > NOTE_MAX:
        raise ValueError(f"Notes can be at most {NOTE_MAX} characters.")
    return note


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
        if raw.get("pet_skin") in PET_SKINS:
            prefs["pet_skin"] = raw["pet_skin"]
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
        elif key == "pet_skin":
            if value not in PET_SKINS:
                raise ValueError(f"pet_skin must be one of {', '.join(PET_SKINS)}")
            prefs[key] = value
        else:
            raise ValueError(f"unknown ui pref: {key}")
    return prefs


def get_ui_prefs() -> dict:
    """{lulz, reduce_effects, lulz_sound, liquid_glass, target_hours, pet, pet_name,
    pet_hint_seen, pet_skin}, defaults for anything unset."""
    return _clean_ui_prefs(_read_raw().get("ui_prefs"))


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
    raw = _read_raw().get("achievements_seen")
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

# names printed on the Full (EAS) sheet; "" leaves the line blank
SHEET_NAME_KEYS = ("employee_name", "manager_name")
SHEET_NAME_MAX = 60


def _sheet_name_error(key: str, v) -> str | None:
    """Why *v* can't be stored as *key*, or None when it can."""
    if not isinstance(v, str):
        return f"{key} must be text of at most {SHEET_NAME_MAX} characters"
    if any(unicodedata.category(c) in _BAD_NAME_CATEGORIES or c in _BIDI_CONTROLS for c in v):
        return f"{key} has control characters"
    if len(" ".join(v.split())) > SHEET_NAME_MAX:
        return f"{key} must be text of at most {SHEET_NAME_MAX} characters"
    return None


def get_sheet_names() -> dict:
    """{employee_name, manager_name}: trimmed, "" when unset or unusable."""
    data = _read_raw()
    out = {}
    for key in SHEET_NAME_KEYS:
        v = data.get(key, "")
        out[key] = "" if _sheet_name_error(key, v) else " ".join(v.split())
    return out


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
    elif key in SHEET_NAME_KEYS:
        problem = _sheet_name_error(key, value)
        if problem:
            raise ValueError(problem)
    elif key != "ui_prefs":
        raise ValueError(f"unknown setting: {key}")


def save_settings(values: dict):
    """Write several settings in one load/save, so either all or none of
    them are stored. Keys are the data.json names (pay_rate,
    default_start_time, default_job_shift, export_format,
    export_include_pay, appearance_mode, employee_name, manager_name,
    ui_prefs — which may be partial).
    Raises ValueError, writing nothing, for a bad key or value."""
    for key, value in values.items():
        _check_setting(key, value)
    data = _load_raw()
    for key, value in values.items():
        if key == "ui_prefs":
            value = merge_ui_prefs(data.get("ui_prefs"), value)
        elif key == "pay_rate":
            value = float(value)
        elif key in SHEET_NAME_KEYS:
            value = " ".join(value.split())
        data[key] = value
    _save_raw(data)


ERROR_LOG = os.path.join(DATA_DIR, "error.log")
_ERROR_LOG_MAX = 256 * 1024
_ERROR_LOG_LOCK = threading.Lock()


def append_error_log(text: str):
    """Append a timestamped traceback to error.log next to data.json (the
    exe has no console). Once over _ERROR_LOG_MAX, the older half is
    dropped. Never raises. Serialised, so threads logging at once can't
    interleave lines or race the trim."""
    try:
        with _ERROR_LOG_LOCK:
            if os.path.exists(ERROR_LOG) and os.path.getsize(ERROR_LOG) > _ERROR_LOG_MAX:
                with open(ERROR_LOG, "r", encoding="utf-8", errors="replace") as f:
                    kept = f.read()[-_ERROR_LOG_MAX // 2:]
                with open(ERROR_LOG, "w", encoding="utf-8") as f:
                    f.write(kept)
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.now().isoformat(timespec='seconds')}\n{text.rstrip()}\n")
    except OSError:
        pass
