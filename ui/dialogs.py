"""Small modal dialogs: month picker and entry add/edit."""
from datetime import date

import customtkinter as ctk
from tkinter import messagebox

import storage
from utils import parse_time_input
from ui import theme


class MonthPickerDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_year: int, current_month: int):
        super().__init__(parent)
        self.title("Jump to month")
        self.geometry("260x150")
        self.resizable(False, False)
        self.grab_set()
        self.result: tuple[int, int] | None = None

        ctk.CTkLabel(self, text="Month").pack(pady=(14, 2))
        self._month_var = ctk.StringVar(value=theme.MONTHS[current_month - 1])
        ctk.CTkOptionMenu(self, variable=self._month_var,
                          values=theme.MONTHS, width=220).pack()

        ctk.CTkLabel(self, text="Year").pack(pady=(8, 2))
        self._year_var = ctk.StringVar(value=str(current_year))
        ctk.CTkEntry(self, textvariable=self._year_var, width=220).pack()

        ctk.CTkButton(self, text="Go", width=220, height=34,
                      command=self._go).pack(pady=10)

    def _go(self):
        try:
            year = int(self._year_var.get().strip())
            month = theme.MONTHS.index(self._month_var.get()) + 1
            self.result = (year, month)
        except (ValueError, IndexError):
            pass
        self.destroy()


class EditEntryDialog(ctk.CTkToplevel):
    def __init__(self, parent, entry: storage.WorkEntry | None = None,
                 default_date: date | None = None):
        super().__init__(parent)
        self.title("Edit Entry" if entry else "Add Entry")
        self.geometry("360x300")
        self.resizable(False, False)
        self.grab_set()
        self.result: storage.WorkEntry | None = None
        self._entry = entry

        pad = {"padx": 20, "pady": 5}

        ctk.CTkLabel(self, text="Date (YYYY-MM-DD)",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._date_var = ctk.StringVar(value=(
            entry.date if entry else (default_date or date.today()).isoformat()
        ))
        ctk.CTkEntry(self, textvariable=self._date_var, width=320).pack(padx=20)

        ctk.CTkLabel(self, text="Job / Shift",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        options = storage.get_job_shift_history()
        self._shift_var = ctk.StringVar(value=(entry.job_shift if entry else options[0]))
        ctk.CTkComboBox(self, variable=self._shift_var, values=options,
                        width=320).pack(padx=20)

        time_row = ctk.CTkFrame(self, fg_color="transparent")
        time_row.pack(padx=20, pady=5, fill="x")

        left = ctk.CTkFrame(time_row, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(left, text="Time In (HH:MM)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self._time_in_var = ctk.StringVar(value=(entry.time_in if entry else "09:00"))
        ctk.CTkEntry(left, textvariable=self._time_in_var).pack(fill="x")

        right = ctk.CTkFrame(time_row, fg_color="transparent")
        right.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(right, text="Time Out (HH:MM)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self._time_out_var = ctk.StringVar(value=(entry.time_out if entry else "17:00"))
        ctk.CTkEntry(right, textvariable=self._time_out_var).pack(fill="x")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=14)
        ctk.CTkButton(btn_frame, text="Save", width=130,
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", width=130,
                      fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                      command=self.destroy).pack(side="left", padx=8)

    def _save(self):
        d = self._date_var.get().strip()
        try:
            date.fromisoformat(d)
        except ValueError:
            messagebox.showerror("Invalid date", "Enter date as YYYY-MM-DD", parent=self)
            return
        t_in = parse_time_input(self._time_in_var.get())
        t_out_raw = self._time_out_var.get().strip()
        t_out = parse_time_input(t_out_raw) if t_out_raw else ""
        if t_in is None:
            messagebox.showerror("Invalid time",
                                 "Time In must be a valid time (e.g. 09:30).", parent=self)
            return
        if t_out_raw and t_out is None:
            messagebox.showerror("Invalid time",
                                 "Time Out must be a valid time (e.g. 17:00).", parent=self)
            return
        self.result = storage.WorkEntry(
            id=self._entry.id if self._entry else storage.new_entry_id(),
            date=d,
            job_shift=self._shift_var.get().strip(),
            time_in=t_in,
            time_out=t_out,
        )
        self.destroy()
