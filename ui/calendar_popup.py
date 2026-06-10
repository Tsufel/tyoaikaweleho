"""Small popup calendar for picking a date with a click."""
import calendar
from datetime import date

import customtkinter as ctk

from ui import theme

_WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


class CalendarPopup(ctk.CTkToplevel):
    """Month-grid date picker. After wait_window(), .result holds the
    clicked date, or None when dismissed."""

    def __init__(self, parent, initial: date | None = None,
                 anchor_widget=None):
        super().__init__(parent)
        self.title("Pick a date")
        self.resizable(False, False)
        self.grab_set()
        self.result: date | None = None

        initial = initial or date.today()
        self._selected = initial
        self._year = initial.year
        self._month = initial.month

        # ── Month navigation header ───────────────────────────
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkButton(nav, text="◄", width=32, height=28,
                      command=self._prev_month).pack(side="left")
        self._title = ctk.CTkLabel(nav, text="",
                                   font=ctk.CTkFont(size=13, weight="bold"))
        self._title.pack(side="left", expand=True)
        ctk.CTkButton(nav, text="►", width=32, height=28,
                      command=self._next_month).pack(side="right")

        # ── Day grid ──────────────────────────────────────────
        self._grid = ctk.CTkFrame(self, fg_color="transparent")
        self._grid.pack(padx=10, pady=(0, 10))
        self._build_grid()

        self.bind("<Escape>", lambda _e: self.destroy())

        # Position next to the anchor widget (clamped to the screen)
        self.update_idletasks()
        if anchor_widget is not None:
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            x = max(0, min(x, self.winfo_screenwidth() - w))
            y = max(0, min(y, self.winfo_screenheight() - h))
            self.geometry(f"+{x}+{y}")

    # ── Navigation ───────────────────────────────────────────────

    def _prev_month(self):
        if self._month == 1:
            self._month, self._year = 12, self._year - 1
        else:
            self._month -= 1
        self._build_grid()

    def _next_month(self):
        if self._month == 12:
            self._month, self._year = 1, self._year + 1
        else:
            self._month += 1
        self._build_grid()

    # ── Grid ─────────────────────────────────────────────────────

    def _build_grid(self):
        self._title.configure(
            text=f"{theme.MONTHS[self._month - 1]} {self._year}")
        for w in self._grid.winfo_children():
            w.destroy()

        for col, name in enumerate(_WEEKDAYS):
            ctk.CTkLabel(self._grid, text=name, width=34,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=theme.GRAY).grid(row=0, column=col,
                                                     padx=1, pady=(0, 2))

        today = date.today()
        for row, week in enumerate(calendar.monthcalendar(self._year, self._month),
                                   start=1):
            for col, day in enumerate(week):
                if day == 0:
                    continue
                d = date(self._year, self._month, day)
                if d == self._selected:
                    fg, border = theme.GREEN, 0
                elif d == today:
                    fg, border = "transparent", 1
                else:
                    fg, border = "transparent", 0
                ctk.CTkButton(
                    self._grid, text=str(day), width=34, height=30,
                    fg_color=fg,
                    hover_color=theme.GREEN_HOVER,
                    border_width=border, border_color=theme.BLUE,
                    text_color=("black", "white") if fg == "transparent" else "white",
                    command=lambda d=d: self._pick(d),
                ).grid(row=row, column=col, padx=1, pady=1)

    def _pick(self, d: date):
        self.result = d
        self.destroy()
