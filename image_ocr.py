"""image_ocr.py — Image OCR DLC for Työaikaweleho
Optional — drop this file in the app folder and restart to activate the
'Import from Image' button.

Requirements:
    pip install pytesseract pillow
    Tesseract-OCR binary: https://github.com/UB-Mannheim/tesseract/wiki
    (During Tesseract setup, tick Add to PATH + Finnish language data)
"""
import re
import os
import shutil
from datetime import date as _date

try:
    import pytesseract
    from PIL import Image
except ImportError as _e:
    raise ImportError(
        "Image OCR DLC requires pytesseract and Pillow.\n"
        "Run: pip install pytesseract pillow"
    ) from _e

import customtkinter as ctk
from tkinter import messagebox
import storage


# ── Tesseract PATH fallback (common Windows install location) ─────────────────
if shutil.which("tesseract") is None:
    _fallback = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_fallback):
        pytesseract.pytesseract.tesseract_cmd = _fallback


def _get_tess_config() -> str:
    """Return the best available Tesseract config (prefer fin+eng, fall back)."""
    try:
        langs = pytesseract.get_languages(config="")
        if "fin" in langs:
            return "--psm 6 -l fin+eng"
    except Exception:
        pass
    return "--psm 6"


# ── Constants ─────────────────────────────────────────────────────────────────
_KNOWN_SHIFTS = {"GPSR", "Sales", "Sales/Support", "Support", "Training", "Onboarding"}
_GRAY         = "#7f8c8d"
_PURPLE       = "#6c3483"
_PURPLE_HOVER = "#512e5f"
_GREEN        = "#27ae60"
_GREEN_HOVER  = "#1e8449"


# ── Regex patterns ────────────────────────────────────────────────────────────
_DATE_ISO  = re.compile(r'\b(\d{4})[.\-/](\d{2})[.\-/](\d{2})\b')
_DATE_DMY  = re.compile(r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b')
_TIME_PAIR = re.compile(
    r'\b(\d{1,2}[:.]\d{2})\s*[-–—]\s*(\d{1,2}[:.]\d{2})\b'
)
_TIME_SOLO = re.compile(r'\b(\d{1,2}[:.]\d{2})\b')
_SHIFT_PAT = re.compile(
    r'\b(GPSR|Sales[/ ]?Support|Sales|Support|Training|Onboarding)\b', re.IGNORECASE
)


# ── Public API (called from app.py) ──────────────────────────────────────────

def extract_entries_from_image(path: str) -> list[dict]:
    """OCR the image at *path* and return a list of candidate entry dicts."""
    img = Image.open(path).convert("L")
    w, h = img.size
    if max(w, h) < 1200:
        scale = 1200 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    config = _get_tess_config()
    text   = pytesseract.image_to_string(img, config=config)
    results = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            entry = _parse_line(line)
            if entry:
                results.append(entry)
    return results


def save_confirmed_entries(entries: list[dict]) -> tuple[int, int]:
    """Save confirmed entries to storage.  Returns (imported, skipped)."""
    existing      = storage.load_all_entries()
    existing_keys = {(e.date, e.time_in) for e in existing}

    imported = skipped = 0
    for e in entries:
        time_in  = _normalise_time(e.get("time_in",  ""))
        time_out = _normalise_time(e.get("time_out", ""))
        date_str = e.get("date", "").strip()

        if not date_str or not time_in:
            skipped += 1
            continue
        try:
            _date.fromisoformat(date_str)
        except ValueError:
            skipped += 1
            continue

        key = (date_str, time_in)
        if key in existing_keys:
            skipped += 1
            continue

        storage.save_entry(storage.WorkEntry(
            id=storage.new_entry_id(),
            date=date_str,
            job_shift=e.get("job_shift", "GPSR") or "GPSR",
            time_in=time_in,
            time_out=time_out,
        ))
        existing_keys.add(key)
        imported += 1

    return imported, skipped


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise_time(t: str) -> str:
    """Normalise OCR-extracted time to HH:MM, or '' if unparseable."""
    t = t.strip().replace(".", ":").replace(",", ":")
    parts = t.split(":")
    if len(parts) != 2:
        return ""
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return ""


def _parse_line(line: str) -> dict | None:
    """Try to extract a timesheet entry from a single OCR text line."""
    date_str = ""

    # ISO date first (unambiguous)
    m = _DATE_ISO.search(line)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        date_str = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    else:
        m = _DATE_DMY.search(line)
        if m:
            d, mo, y = m.group(1), m.group(2), m.group(3)
            if len(y) == 2:
                y = "20" + y
            date_str = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"

    if date_str:
        try:
            parsed = _date.fromisoformat(date_str)
            if not (2020 <= parsed.year <= 2035):
                date_str = ""
        except ValueError:
            date_str = ""

    if not date_str:
        return None   # no recognisable date → skip this line entirely

    # Times
    time_in = time_out = ""
    pair = _TIME_PAIR.search(line)
    if pair:
        time_in  = _normalise_time(pair.group(1))
        time_out = _normalise_time(pair.group(2))
    else:
        solos = [t for t in _TIME_SOLO.findall(line) if _normalise_time(t)]
        if solos:
            time_in = _normalise_time(solos[0])
        if len(solos) > 1:
            time_out = _normalise_time(solos[1])

    # Shift
    sm = _SHIFT_PAT.search(line)
    if sm:
        raw = sm.group(0).strip()
        job_shift = next(
            (s for s in _KNOWN_SHIFTS if s.lower() == raw.lower()), raw.title()
        )
    else:
        job_shift = "GPSR"

    return {
        "date":        date_str,
        "job_shift":   job_shift,
        "time_in":     time_in,
        "time_out":    time_out,
        "_raw_line":   line,
        "_confidence": "ok" if (date_str and time_in) else "uncertain",
    }


# ── Preview dialog ────────────────────────────────────────────────────────────

class OcrPreviewDialog(ctk.CTkToplevel):
    """Shows detected entries in an editable table before importing."""

    def __init__(self, parent, candidates: list[dict]):
        super().__init__(parent)
        self.title(f"OCR Preview — {len(candidates)} entries detected")
        self.geometry("840x540")
        self.minsize(640, 400)
        self.grab_set()
        self.confirmed_entries: list[dict] = []
        self._candidates   = candidates
        self._check_vars:   list[ctk.BooleanVar] = []
        self._row_widgets:  list[dict] = []
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="Review detected entries. Uncheck rows to skip; edit fields as needed.",
            text_color=_GRAY,
            font=ctk.CTkFont(size=11),
        ).pack(padx=16, pady=(12, 4), anchor="w")

        # Fixed column headers
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(0, 2))
        for text, w in [
            ("",     28), ("Date", 110), ("Shift", 130),
            ("In",   72), ("Out",  72),  ("Raw OCR text", 330),
        ]:
            ctk.CTkLabel(
                header, text=text, width=w,
                font=ctk.CTkFont(weight="bold"), anchor="w",
            ).pack(side="left", padx=2)

        # Scrollable entry rows
        self._scroll = ctk.CTkScrollableFrame(self, height=370)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        for i, cand in enumerate(self._candidates):
            self._add_row(i, cand)

        # Bottom action bar
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=10)
        self._import_btn = ctk.CTkButton(
            btn_row,
            text=f"Import Selected ({len(self._candidates)})",
            width=220,
            fg_color=_PURPLE, hover_color=_PURPLE_HOVER,
            command=self._confirm,
        )
        self._import_btn.pack(side="left", padx=8)
        ctk.CTkButton(
            btn_row, text="Cancel", width=100,
            fg_color=_GRAY, hover_color="#636e72",
            command=self.destroy,
        ).pack(side="left", padx=8)
        self._update_btn_label()

    def _add_row(self, idx: int, cand: dict):
        uncertain = cand.get("_confidence") == "uncertain"
        row_frame = ctk.CTkFrame(
            self._scroll,
            fg_color="#3d2b1a" if uncertain else "transparent",
            corner_radius=4,
        )
        row_frame.pack(fill="x", pady=1, padx=2)

        check_var = ctk.BooleanVar(value=True)
        check_var.trace_add("write", lambda *_: self._update_btn_label())
        self._check_vars.append(check_var)
        ctk.CTkCheckBox(row_frame, text="", variable=check_var, width=28).pack(
            side="left", padx=(4, 2)
        )

        date_var  = ctk.StringVar(value=cand.get("date", ""))
        shift_var = ctk.StringVar(value=cand.get("job_shift", "GPSR"))
        in_var    = ctk.StringVar(value=cand.get("time_in",  ""))
        out_var   = ctk.StringVar(value=cand.get("time_out", ""))
        self._row_widgets.append({
            "check":   check_var,
            "date":    date_var,
            "shift":   shift_var,
            "time_in": in_var,
            "time_out": out_var,
        })

        ctk.CTkEntry(row_frame, textvariable=date_var,  width=110).pack(side="left", padx=2)
        ctk.CTkComboBox(
            row_frame, variable=shift_var,
            values=storage.get_job_shift_history(), width=130,
        ).pack(side="left", padx=2)
        ctk.CTkEntry(row_frame, textvariable=in_var,   width=72).pack(side="left", padx=2)
        ctk.CTkEntry(row_frame, textvariable=out_var,  width=72).pack(side="left", padx=2)
        ctk.CTkLabel(
            row_frame,
            text=cand.get("_raw_line", "")[:55],
            width=330, anchor="w",
            text_color=_GRAY, font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(6, 4))

    def _update_btn_label(self):
        count = sum(1 for v in self._check_vars if v.get())
        self._import_btn.configure(text=f"Import Selected ({count})")

    def _confirm(self):
        entries = []
        for w in self._row_widgets:
            if not w["check"].get():
                continue
            entries.append({
                "date":      w["date"].get().strip(),
                "job_shift": w["shift"].get().strip(),
                "time_in":   w["time_in"].get().strip(),
                "time_out":  w["time_out"].get().strip(),
            })

        valid, skipped_count = [], 0
        for e in entries:
            if e["date"] and e["time_in"]:
                valid.append(e)
            else:
                skipped_count += 1

        if skipped_count:
            messagebox.showwarning(
                "Rows skipped",
                f"{skipped_count} row(s) had no date or start time and were skipped.",
                parent=self,
            )
        self.confirmed_entries = valid
        self.destroy()
