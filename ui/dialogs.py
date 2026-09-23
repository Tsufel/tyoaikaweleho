"""Small modal dialogs: month picker, entry add/edit, shift recovery, changelog."""
from datetime import date, datetime

import customtkinter as ctk

import storage
from utils import (parse_time_input, parse_date_input, entry_minutes, is_overnight,
                   is_long_shift, add_hours, format_duration)
from ui import msgbox as messagebox
from ui import theme
from ui.calendar_popup import CalendarPopup
from ui.window_utils import prepare_dialog


class MonthPickerDialog(ctk.CTkToplevel):
    """Up/Down step the month, PageUp/PageDown the year, Enter jumps."""

    def __init__(self, parent, current_year: int, current_month: int):
        super().__init__(parent)
        self.title("Jump to month")
        self.geometry("260x210")
        self.resizable(False, False)
        self.result: tuple[int, int] | None = None

        ctk.CTkLabel(self, text="Month").pack(pady=(14, 2))
        self._month_var = ctk.StringVar(value=theme.MONTHS[current_month - 1])
        ctk.CTkOptionMenu(self, variable=self._month_var,
                          values=theme.MONTHS, width=220).pack()

        ctk.CTkLabel(self, text="Year").pack(pady=(8, 2))
        self._year_var = ctk.StringVar(value=str(current_year))
        self._year_entry = ctk.CTkEntry(self, textvariable=self._year_var, width=220)
        self._year_entry.pack()

        ctk.CTkButton(self, text="Go", width=220, height=34,
                      command=self._go).pack(pady=10)

        self.bind("<Return>", lambda _e: self._go())
        self.bind("<KP_Enter>", lambda _e: self._go())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Up>", lambda _e: self._step(-1))
        self.bind("<Down>", lambda _e: self._step(1))
        self.bind("<Prior>", lambda _e: self._step(-12))
        self.bind("<Next>", lambda _e: self._step(12))
        prepare_dialog(self, parent, focus=self._year_entry)
        self._year_entry.select_range(0, "end")

    def _year(self) -> int | None:
        try:
            year = int(self._year_var.get().strip())
        except ValueError:
            return None
        return year if 1900 <= year <= 9999 else None

    def _step(self, months: int):
        year = self._year() or date.today().year
        index = year * 12 + theme.MONTHS.index(self._month_var.get()) + months
        year, month0 = divmod(index, 12)
        if 1900 <= year <= 9999:
            self._year_var.set(str(year))
            self._month_var.set(theme.MONTHS[month0])
        return "break"

    def _go(self):
        year = self._year()
        if year is None:
            messagebox.showerror("Invalid year",
                                 "Enter a year between 1900 and 9999.", parent=self)
            return
        month = theme.MONTHS.index(self._month_var.get()) + 1
        self.result = (year, month)
        self.destroy()


class EditEntryDialog(ctk.CTkToplevel):
    """Add or edit one entry. With *on_save*, the entry is saved from here
    and the dialog only closes once that succeeded — if it raises OSError
    (data.json locked) the error is shown and everything typed is kept.
    .result is the saved entry, or None if cancelled."""

    def __init__(self, parent, entry: storage.WorkEntry | None = None,
                 default_date: date | None = None, on_save=None):
        super().__init__(parent)
        self.title("Edit Entry" if entry else "Add Entry")
        self.geometry("360x350")
        self.resizable(False, False)
        self.result: storage.WorkEntry | None = None
        self._entry = entry
        self._on_save = on_save

        pad = {"padx": 20, "pady": 5}

        ctk.CTkLabel(self, text="Date  (e.g. 2026-09-23 or 23.9.)",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._date_var = ctk.StringVar(value=(
            entry.date if entry else (default_date or date.today()).isoformat()
        ))
        date_row = ctk.CTkFrame(self, fg_color="transparent")
        date_row.pack(padx=20, fill="x")
        self._date_entry = ctk.CTkEntry(date_row, textvariable=self._date_var, width=276)
        self._date_entry.pack(side="left")
        self._cal_btn = ctk.CTkButton(date_row, text="📅", width=40,
                                      command=self._pick_date)
        self._cal_btn.pack(side="left", padx=(4, 0))

        ctk.CTkLabel(self, text="Job / Shift",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        options = storage.get_job_shift_history()
        if entry:
            job = entry.job_shift
        else:
            job = storage.get_default_job_shift() or (options[0] if options else "")
        self._shift_var = ctk.StringVar(value=job)
        ctk.CTkComboBox(self, variable=self._shift_var, values=options,
                        width=320).pack(padx=20)

        time_row = ctk.CTkFrame(self, fg_color="transparent")
        time_row.pack(padx=20, pady=5, fill="x")

        if entry:
            time_in, time_out = entry.time_in, entry.time_out
        else:
            time_in = storage.get_default_start_time()
            time_out = add_hours(time_in, 8) if parse_time_input(time_in) else ""

        left = ctk.CTkFrame(time_row, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(left, text="Time In (HH:MM)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self._time_in_var = ctk.StringVar(value=time_in)
        ctk.CTkEntry(left, textvariable=self._time_in_var).pack(fill="x")

        right = ctk.CTkFrame(time_row, fg_color="transparent")
        right.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(right, text="Time Out (HH:MM)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self._time_out_var = ctk.StringVar(value=time_out)
        ctk.CTkEntry(right, textvariable=self._time_out_var).pack(fill="x")

        self._duration_label = ctk.CTkLabel(self, text="", anchor="w",
                                            text_color=theme.TEXT_MUTED)
        self._duration_label.pack(padx=20, fill="x")
        for var in (self._time_in_var, self._time_out_var):
            var.trace_add("write", lambda *_a: self._update_duration())
        self._update_duration()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(8, 14))
        ctk.CTkButton(btn_frame, text="Save", width=130,
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", width=130,
                      fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                      command=self.destroy).pack(side="left", padx=8)

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<KP_Enter>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())
        prepare_dialog(self, parent, focus=self._date_entry)

    def _times(self) -> tuple[str | None, str | None]:
        """(time in, time out) parsed; time out is '' when left empty."""
        t_in = parse_time_input(self._time_in_var.get())
        t_out_raw = self._time_out_var.get().strip()
        t_out = parse_time_input(t_out_raw) if t_out_raw else ""
        return t_in, t_out

    def _update_duration(self):
        t_in, t_out = self._times()
        if t_in is None or t_out is None:
            text, color = "Duration: —", theme.TEXT_MUTED
        elif t_out == "":
            text, color = "No time out yet — the shift counts as 0h", theme.TEXT_MUTED
        else:
            minutes = entry_minutes(t_in, t_out)
            text = f"Duration: {format_duration(minutes)}"
            if is_overnight(t_in, t_out):
                text += "  (+1 day)"
            color = theme.TEXT_MUTED
            if is_long_shift(minutes):
                text += "  — unusually long"
                color = theme.TEXT_WARNING
        self._duration_label.configure(text=text, text_color=color)

    def _pick_date(self):
        initial_iso = parse_date_input(self._date_var.get())
        initial = date.fromisoformat(initial_iso) if initial_iso else date.today()
        popup = CalendarPopup(self, initial=initial, anchor_widget=self._cal_btn)
        self.wait_window(popup)
        if popup.result:
            self._date_var.set(popup.result.isoformat())

    def _save(self):
        d = parse_date_input(self._date_var.get())
        if d is None:
            messagebox.showerror("Invalid date",
                                 "Enter the date as YYYY-MM-DD or D.M.YYYY "
                                 "(e.g. 2026-09-23 or 23.9.2026).", parent=self)
            return
        t_in, t_out = self._times()
        if t_in is None:
            messagebox.showerror("Invalid time",
                                 "Time In must be a valid time (e.g. 09:30).", parent=self)
            return
        if t_out is None:
            messagebox.showerror("Invalid time",
                                 "Time Out must be a valid time (e.g. 17:00).", parent=self)
            return
        if t_out:
            minutes = entry_minutes(t_in, t_out)
            if is_long_shift(minutes) and not messagebox.askyesno(
                    "Long shift",
                    f"{t_in}–{t_out} is {format_duration(minutes)}"
                    f"{' (ending the next day)' if is_overnight(t_in, t_out) else ''}."
                    "\n\nSave it anyway?",
                    icon="warning", parent=self):
                return
        entry = storage.WorkEntry(
            id=self._entry.id if self._entry else storage.new_entry_id(),
            date=d,
            job_shift=self._shift_var.get().strip(),
            time_in=t_in,
            time_out=t_out,
        )
        if self._on_save is not None:
            try:
                self._on_save(entry)
            except OSError as exc:
                messagebox.showerror(
                    "Could not save entry",
                    f"The entry could not be saved:\n\n{exc}\n\n"
                    "Close any program that may be locking data.json and "
                    "press Save again.", parent=self)
                return
        self.result = entry
        self.destroy()


class RecoverShiftDialog(ctk.CTkToplevel):
    """Shown on startup when session.json holds an unfinished shift.

    result is "resume", "discard" or ("save", "HH:MM"). Closing the window
    or pressing Escape resumes, so the session is never lost by accident.
    """

    def __init__(self, parent, start_dt: datetime, job_shift: str,
                 suggested_end: str, over_limit: bool):
        super().__init__(parent)
        self.title("Recover shift")
        self.geometry("380x330")
        self.resizable(False, False)
        self.result: str | tuple[str, str] = "resume"

        elapsed = datetime.now() - start_dt
        h = int(elapsed.total_seconds() // 3600)
        m = int((elapsed.total_seconds() % 3600) // 60)

        ctk.CTkLabel(self, text="An unfinished shift was found",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(16, 8))

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(padx=24, fill="x")
        rows = [("Date", start_dt.strftime("%a %Y-%m-%d")),
                ("Job / Shift", job_shift),
                ("Started", start_dt.strftime("%H:%M")),
                ("Elapsed", f"{h}h {m:02d}m")]
        for r, (label, value) in enumerate(rows):
            ctk.CTkLabel(info, text=label + ":", anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, 12))
            ctk.CTkLabel(info, text=value, anchor="w",
                         font=ctk.CTkFont(weight="bold")).grid(row=r, column=1, sticky="w")

        if over_limit:
            ctk.CTkLabel(self, text="Over 8 hours — end time set to the 8-hour mark.",
                         text_color=theme.TEXT_WARNING,
                         font=ctk.CTkFont(size=11)).pack(pady=(8, 0))

        end_row = ctk.CTkFrame(self, fg_color="transparent")
        end_row.pack(pady=(10, 0))
        ctk.CTkLabel(end_row, text="End time (for Save):").pack(side="left", padx=(0, 8))
        self._end_var = ctk.StringVar(value=suggested_end)
        end_entry = ctk.CTkEntry(end_row, textvariable=self._end_var, width=80,
                                 justify="center")
        end_entry.pack(side="left")
        # Enter after typing an end time means "save with it"
        end_entry.bind("<Return>", lambda _e: self._save())
        end_entry.bind("<KP_Enter>", lambda _e: self._save())

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=18)
        ctk.CTkButton(btns, text="▶  Resume", width=105,
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self._resume).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="💾  Save", width=105,
                      command=self._save).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="🗑  Discard", width=105,
                      fg_color=theme.RED, hover_color=theme.RED_HOVER,
                      command=self._discard).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._resume)
        self.bind("<Escape>", lambda _e: self._resume())
        prepare_dialog(self, parent)

    def _resume(self):
        self.result = "resume"
        self.destroy()

    def _save(self):
        end = parse_time_input(self._end_var.get())
        if end is None:
            messagebox.showerror("Invalid time",
                                 "End time must be a valid time (e.g. 17:00).", parent=self)
            return
        self.result = ("save", end)
        self.destroy()

    def _discard(self):
        if messagebox.askyesno("Discard shift",
                               "Discard this shift? It will not be saved.",
                               icon="warning", parent=self):
            self.result = "discard"
            self.destroy()


class ChangelogDialog(ctk.CTkToplevel):
    """'What's new' dialog shown once on first launch after an update."""

    def __init__(self, parent, entries: dict[str, list[str]]):
        super().__init__(parent)
        from version import __version__
        self.title(f"What's new in v{__version__}")
        self.geometry("480x380")
        self.resizable(False, False)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(16, 8))

        def _ver_key(kv):
            try:
                return tuple(int(x) for x in kv[0].split("."))
            except ValueError:
                return (0, 0, 0)

        for ver, items in sorted(entries.items(), key=_ver_key, reverse=True):
            ctk.CTkLabel(scroll, text=f"v{ver}",
                         font=ctk.CTkFont(weight="bold", size=14)).pack(anchor="w", pady=(4, 2))
            for item in items:
                ctk.CTkLabel(scroll, text=f"  • {item}",
                             wraplength=420, justify="left",
                             anchor="w").pack(anchor="w", pady=1)
            ctk.CTkLabel(scroll, text="").pack()   # spacer between versions

        ctk.CTkButton(self, text="Got it  ✓", width=140,
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self.destroy).pack(pady=(0, 16))

        for seq in ("<Return>", "<KP_Enter>", "<Escape>"):
            self.bind(seq, lambda _e: self.destroy())
        prepare_dialog(self, parent)
