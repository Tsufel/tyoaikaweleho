"""Entries table: monthly shift list with week totals and inline editing."""
from datetime import date

import tkinter as tk
import customtkinter as ctk
from tkinter import ttk

import storage
from utils import parse_time_input


class EntriesTable(ctk.CTkFrame):
    """Treeview of one month's entries grouped by ISO week.

    on_change() is called after an inline edit has been saved, so the
    parent can refresh totals.
    """

    def __init__(self, master, on_change, on_activate):
        super().__init__(master, corner_radius=8)
        self._on_change = on_change

        cols = ("date", "shift", "time_in", "time_out", "hours")
        self._tree = ttk.Treeview(self, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.tag_configure("odd", background="#f0f4f8")
        self._tree.tag_configure("even", background="#ffffff")
        self._tree.tag_configure("week_total",
                                 background="#dce8f5",
                                 font=("Arial", 10, "bold"))

        specs = [
            ("date",     "Date",        150, "w"),
            ("shift",    "Job / Shift",  130, "center"),
            ("time_in",  "Time In",      90, "center"),
            ("time_out", "Time Out",     90, "center"),
            ("hours",    "Hours",        80, "center"),
        ]
        for col, text, width, anchor in specs:
            self._tree.heading(col, text=text)
            self._tree.column(col, width=width, anchor=anchor, minwidth=60)

        sb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        self._tree.bind("<Double-1>", lambda _e: on_activate())
        self._tree.bind("<ButtonRelease-1>", self._on_cell_click)
        self._inline_editor: tk.Entry | None = None

    # ── Public API ───────────────────────────────────────────────

    def selected_entry_id(self) -> str | None:
        """Return the id of the selected entry row, or None when nothing
        (or a week-total row) is selected."""
        sel = self._tree.selection()
        if not sel or sel[0].startswith("week_"):
            return None
        return sel[0]

    def refresh(self, year: int, month: int) -> int:
        """Reload the table for the given month. Returns total minutes."""
        for row in self._tree.get_children():
            self._tree.delete(row)

        entries = storage.load_month(year, month)
        rate = storage.get_pay_rate()

        # Group by ISO week number
        by_week: dict[int, list] = {}
        for e in entries:
            wk = date.fromisoformat(e.date).isocalendar()[1]
            by_week.setdefault(wk, []).append(e)

        total_minutes = 0
        row_idx = 0

        for wk in sorted(by_week):
            week_entries = by_week[wk]
            week_minutes = 0

            for e in week_entries:
                hours_str = ""
                if e.time_in and e.time_out:
                    mins = _entry_minutes(e)
                    week_minutes += mins
                    h, m = divmod(mins, 60)
                    hours_str = f"{h}:{m:02d}"

                d = date.fromisoformat(e.date)
                display_date = d.strftime("%a %d %b %Y")
                tag = "odd" if row_idx % 2 == 0 else "even"
                self._tree.insert("", "end", iid=e.id,
                                  values=(display_date, e.job_shift,
                                          e.time_in, e.time_out, hours_str),
                                  tags=(tag,))
                row_idx += 1

            total_minutes += week_minutes
            wh, wm = divmod(week_minutes, 60)
            week_earn = week_minutes / 60 * rate
            self._tree.insert("", "end", iid=f"week_{wk}",
                              values=(f"── Week {wk} total", "", "", "",
                                      f"{wh}:{wm:02d}  (€{week_earn:.2f})"),
                              tags=("week_total",))

        return total_minutes

    # ── Inline cell editing ──────────────────────────────────────

    def _on_cell_click(self, event):
        if self._inline_editor:
            # Let FocusOut on the existing editor handle saving first
            return

        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        col = self._tree.identify_column(event.x)   # "#1".."#5"
        row_id = self._tree.identify_row(event.y)

        if not row_id or row_id.startswith("week_"):
            return

        # Only Time In (#3) and Time Out (#4) are inline-editable
        col_map = {"#3": "time_in", "#4": "time_out"}
        if col not in col_map:
            return

        field = col_map[col]
        bbox = self._tree.bbox(row_id, col)
        if not bbox:
            return
        x, y, w, h = bbox

        values = self._tree.item(row_id, "values")
        col_idx = int(col[1:]) - 1
        current = values[col_idx] if col_idx < len(values) else ""

        editor = tk.Entry(self._tree, font=("Arial", 10),
                          justify="center", relief="flat",
                          highlightthickness=1,
                          highlightbackground="#1f538d",
                          highlightcolor="#1f538d")
        editor.insert(0, current)
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()
        self._inline_editor = editor

        def commit(e=None):
            if self._inline_editor is None:
                return
            new_val = editor.get().strip()
            self._inline_editor = None
            editor.destroy()
            parsed = parse_time_input(new_val)
            if parsed is None or parsed == current:
                self._on_change()
                return
            all_entries = storage.load_all_entries()
            entry = next((en for en in all_entries if en.id == row_id), None)
            if entry:
                setattr(entry, field, parsed)
                storage.update_entry(entry)
            self._on_change()

        def cancel(e=None):
            self._inline_editor = None
            editor.destroy()

        editor.bind("<Return>", commit)
        editor.bind("<Tab>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", cancel)


def _entry_minutes(e: storage.WorkEntry) -> int:
    try:
        ih, im = map(int, e.time_in.split(":"))
        oh, om = map(int, e.time_out.split(":"))
        return max(0, (oh * 60 + om) - (ih * 60 + im))
    except Exception:
        return 0
