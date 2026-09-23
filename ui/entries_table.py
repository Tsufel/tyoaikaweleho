"""Entries table: monthly shift list with week totals and inline editing."""
import traceback
from datetime import date

import tkinter as tk
import customtkinter as ctk
from tkinter import ttk

import storage
from ui import msgbox as messagebox
from ui import theme
from utils import (parse_time_input, entry_minutes, is_overnight, week_key,
                   is_long_shift, format_duration)

# Only Time In (#3) and Time Out (#4) are inline-editable
_EDITABLE = {"#3": "time_in", "#4": "time_out"}


class EntriesTable(ctk.CTkFrame):
    """Treeview of one month's entries grouped by ISO week.

    on_change() is called after an inline edit has been saved, so the
    parent can refresh totals. on_activate() / on_delete() are Enter/F2 and
    Delete on a row, on_select() fires when the selection changes, and
    on_status(msg) shows a short note (e.g. a rejected inline edit).
    """

    def __init__(self, master, on_change, on_activate, on_delete=None,
                 on_select=None, on_status=None):
        super().__init__(master, corner_radius=8)
        self._on_change = on_change
        self._on_status = on_status or (lambda _msg: None)
        self._shown_month: tuple[int, int] | None = None

        cols = ("date", "shift", "time_in", "time_out", "hours")
        self._tree = ttk.Treeview(self, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.tag_configure("week_total", font=("Arial", 10, "bold"))

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

        self._scrollbar = ctk.CTkScrollbar(self, command=self._tree.yview)
        self._tree.configure(yscrollcommand=self._on_yscroll)
        self._tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self._scrollbar.pack(side="right", fill="y", pady=2)

        field = (theme.TABLE["light"]["field"], theme.TABLE["dark"]["field"])
        self._empty_label = ctk.CTkLabel(self._tree, text="", fg_color=field,
                                         bg_color=field, corner_radius=0,
                                         text_color=theme.TEXT_MUTED,
                                         justify="center")

        self._on_activate = on_activate
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Return>", lambda _e: on_activate())
        self._tree.bind("<KP_Enter>", lambda _e: on_activate())
        self._tree.bind("<F2>", lambda _e: on_activate())
        if on_delete is not None:
            self._tree.bind("<Delete>", lambda _e: on_delete())
        if on_select is not None:
            self._tree.bind("<<TreeviewSelect>>", lambda _e: on_select())
        self._tree.bind("<ButtonPress-1>", self._on_press)
        self._tree.bind("<ButtonRelease-1>", self._on_cell_click)
        self._tree.bind("<Motion>", self._update_cursor)
        self._tree.bind("<Configure>", lambda _e: self._reposition_editor(), add="+")

        self._inline_editor: tk.Entry | None = None
        self._editor_cell: tuple[str, str] | None = None   # (row id, "#3"/"#4")
        self._editor_original = ""
        self._editor_invalid = False
        self._press_cell: tuple[str, str] | None = None
        self._restyle()

    # ── Appearance ───────────────────────────────────────────────

    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        self._restyle()

    def _restyle(self):
        # CTk swallows exceptions from appearance callbacks; at least log them
        try:
            mode = self._get_appearance_mode()
            theme.apply_table_style(self._tree, mode)
            if self._inline_editor is not None:
                self._inline_editor.configure(
                    **theme.entry_colors(mode, invalid=self._editor_invalid))
        except Exception:
            storage.append_error_log(traceback.format_exc())

    # ── Public API ───────────────────────────────────────────────

    def selected_entry_id(self) -> str | None:
        """Return the id of the selected entry row, or None when nothing
        (or a week-total row) is selected."""
        sel = self._tree.selection()
        if not sel or sel[0].startswith("week_"):
            return None
        return sel[0]

    def select_entry(self, entry_id: str):
        """Select, focus and scroll to an entry row, if it's shown."""
        if not self._tree.exists(entry_id):
            return
        self._tree.selection_set(entry_id)
        self._tree.focus(entry_id)
        self._tree.see(entry_id)

    def focus_table(self):
        self._tree.focus_set()

    def commit_edit(self) -> bool:
        """Save (or, if invalid, drop) an open inline edit. False if it
        could not be saved and the editor is still open."""
        return self._close_editor(commit=True)

    def refresh(self, year: int, month: int, select: str | None = None) -> int:
        """Reload the table for the given month. Returns total minutes.

        Within the same month the selection and scroll position are kept;
        *select* (an entry id) is selected and scrolled into view instead.
        """
        self._close_editor(commit=True)
        same_month = self._shown_month == (year, month)
        keep = select
        if keep is None and same_month:
            sel = self._tree.selection()
            keep = sel[0] if sel else None
        yview = self._tree.yview()[0] if same_month else 0.0

        for row in self._tree.get_children():
            self._tree.delete(row)

        entries = storage.load_month(year, month)
        rate = storage.get_pay_rate()

        # Group by (ISO year, ISO week) so early-January days that belong
        # to last year's week 52/53 sort before week 1
        by_week: dict[tuple[int, int], list] = {}
        for e in entries:
            by_week.setdefault(week_key(date.fromisoformat(e.date)), []).append(e)

        total_minutes = 0
        row_idx = 0

        for key in sorted(by_week):
            week_entries = by_week[key]
            iso_year, wk = key
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
                time_out_display = e.time_out
                if e.time_in and e.time_out and is_overnight(e.time_in, e.time_out):
                    time_out_display = e.time_out + " +1"
                tag = "odd" if row_idx % 2 == 0 else "even"
                self._tree.insert("", "end", iid=e.id,
                                  values=(display_date, e.job_shift,
                                          e.time_in, time_out_display, hours_str),
                                  tags=(tag,))
                row_idx += 1

            total_minutes += week_minutes
            wh, wm = divmod(week_minutes, 60)
            week_earn = week_minutes / 60 * rate
            self._tree.insert("", "end", iid=f"week_{iso_year}_{wk}",
                              values=(f"── Week {wk} total", "", "", "",
                                      f"{wh}:{wm:02d}  (€{week_earn:.2f})"),
                              tags=("week_total",))

        self._shown_month = (year, month)
        self._tree.yview_moveto(yview)
        if keep and self._tree.exists(keep):
            self._tree.selection_set(keep)
            self._tree.focus(keep)
            if select:
                self._tree.see(keep)

        if entries:
            self._empty_label.place_forget()
        else:
            name = date(year, month, 1).strftime("%B %Y")
            self._empty_label.configure(
                text=f"No shifts in {name}.\nPress START or + Add entry.")
            self._empty_label.place(relx=0.5, rely=0.5, anchor="center")
        return total_minutes

    # ── Inline cell editing ──────────────────────────────────────

    def _editable_cell(self, x: int, y: int) -> tuple[str, str] | None:
        if self._tree.identify_region(x, y) != "cell":
            return None
        col = self._tree.identify_column(x)   # "#1".."#5"
        row_id = self._tree.identify_row(y)
        if not row_id or row_id.startswith("week_") or col not in _EDITABLE:
            return None
        return row_id, col

    def _update_cursor(self, event):
        cursor = "xterm" if self._editable_cell(event.x, event.y) else ""
        if str(self._tree.cget("cursor")) != cursor:
            self._tree.configure(cursor=cursor)

    def _on_double_click(self, event):
        # only on the row itself, not a heading or the empty space below
        if (self._tree.identify_region(event.x, event.y) == "cell"
                and self._tree.identify_row(event.y) == self.selected_entry_id()):
            self._on_activate()

    def _on_press(self, event):
        # Remembered before the click can save an open edit: that save
        # refreshes the table and may re-sort the rows, so by the release the
        # row under the mouse can be a different entry
        self._press_cell = self._editable_cell(event.x, event.y)

    def _on_cell_click(self, _event):
        cell, self._press_cell = self._press_cell, None
        if self._inline_editor is not None:
            if cell == self._editor_cell:
                return
            # clicking elsewhere saves the open edit first
            if not self._close_editor(commit=True):
                return
        if cell is None or not self._tree.exists(cell[0]):
            return
        row_id, col = cell
        values = self._tree.item(row_id, "values")
        col_idx = int(col[1:]) - 1
        current = str(values[col_idx]) if col_idx < len(values) else ""
        self._open_editor(row_id, col, current.split(" ")[0])

    def _open_editor(self, row_id: str, col: str, text: str, original: str | None = None):
        if not self._tree.exists(row_id):
            return
        bbox = self._tree.bbox(row_id, col)
        if not bbox:                # scrolled out of view
            self._tree.see(row_id)
            self._tree.update_idletasks()
            bbox = self._tree.bbox(row_id, col)
            if not bbox:
                return
        if self._inline_editor is not None:
            self._inline_editor.destroy()
        x, y, w, h = bbox
        editor = tk.Entry(self._tree, font=("Arial", 10), justify="center",
                          relief="flat", borderwidth=0, highlightthickness=2,
                          **theme.entry_colors(self._get_appearance_mode()))
        editor.insert(0, text)
        editor.select_range(0, "end")
        editor.icursor("end")
        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()
        self._inline_editor = editor
        self._editor_cell = (row_id, col)
        self._editor_original = text if original is None else original
        self._editor_invalid = False

        editor.bind("<Return>", self._on_editor_return)
        editor.bind("<KP_Enter>", self._on_editor_return)
        editor.bind("<Tab>", self._on_editor_tab)
        editor.bind("<Escape>", lambda _e: (self._close_editor(commit=False),
                                            self._tree.focus_set(), "break")[-1])
        editor.bind("<FocusOut>", lambda _e: self.after(10, self._check_editor_focus))
        editor.bind("<KeyRelease>", self._revalidate_editor)
        editor.bind("<MouseWheel>", lambda _e: self._close_editor(commit=True))

    def _editor_value(self) -> str:
        parts = self._inline_editor.get().split()
        return parts[0] if parts else ""       # drop a pasted " +1" suffix

    def _on_editor_return(self, _event=None):
        if self._close_editor(commit=True, strict=True):
            self._tree.focus_set()
        return "break"

    def _on_editor_tab(self, _event=None):
        if self._close_editor(commit=True):
            self._tree.focus_set()
        return "break"

    def _revalidate_editor(self, _event=None):
        if (self._inline_editor is not None and self._editor_invalid
                and parse_time_input(self._editor_value()) is not None):
            self._editor_invalid = False
            self._inline_editor.configure(**theme.entry_colors(self._get_appearance_mode()))

    def _check_editor_focus(self):
        """Deferred FocusOut: save when focus moved elsewhere in the app, but
        keep the editor when the whole app lost focus (Alt+Tab) — the user
        may still be typing."""
        editor = self._inline_editor
        if editor is None:
            return
        try:
            focused = self.focus_get()
        except KeyError:            # focus in a Tk-internal widget
            focused = self
        if focused is None or focused is editor:
            return
        self._close_editor(commit=True)

    def _reposition_editor(self):
        if self._inline_editor is None:
            return
        row_id, col = self._editor_cell
        bbox = self._tree.bbox(row_id, col) if self._tree.exists(row_id) else ""
        if not bbox:                # scrolled out of view
            self._close_editor(commit=True)
            return
        x, y, w, h = bbox
        self._inline_editor.place(x=x, y=y, width=w, height=h)

    def _on_yscroll(self, first, last):
        self._scrollbar.set(first, last)
        if self._inline_editor is not None:
            self.after_idle(self._reposition_editor)

    def _close_editor(self, commit: bool, strict: bool = False) -> bool:
        """Close the inline editor, saving its value if *commit*. An invalid
        value is refused: with *strict* (Enter) the editor stays open and
        turns red; otherwise it reverts with a status note. Returns True if
        the editor is closed."""
        editor = self._inline_editor
        if editor is None:
            return True
        text = self._editor_value()
        parsed = parse_time_input(text) if commit else None
        if commit and parsed is None and text != self._editor_original:
            if strict:
                self._editor_invalid = True
                editor.configure(**theme.entry_colors(self._get_appearance_mode(),
                                                      invalid=True))
                editor.select_range(0, "end")
                return False
            self._on_status("Invalid time, not saved")

        row_id, col = self._editor_cell
        self._inline_editor = None
        self._editor_cell = None
        editor.destroy()
        if parsed is None or parsed == self._editor_original:
            return True

        entry = next((en for en in storage.load_all_entries() if en.id == row_id), None)
        if entry is None:
            return True
        setattr(entry, _EDITABLE[col], parsed)
        if entry.time_in and entry.time_out:
            minutes = _entry_minutes(entry)
            overnight = is_overnight(entry.time_in, entry.time_out)
            if is_long_shift(minutes) and not messagebox.askyesno(
                    "Long shift",
                    f"{entry.time_in}–{entry.time_out} is {format_duration(minutes)}"
                    f"{' (ending the next day)' if overnight else ''}."
                    "\n\nSave it anyway?",
                    icon="warning", parent=self):
                self._open_editor(row_id, col, text, original=self._editor_original)
                return False
        try:
            storage.update_entry(entry)
        except OSError as exc:
            messagebox.showerror("Could not save change",
                                 f"The change could not be saved:\n\n{exc}\n\n"
                                 "Close any program using data.json and try again.",
                                 parent=self)
            # give the typed value back so it isn't lost
            self._open_editor(row_id, col, text, original=self._editor_original)
            return False
        self._on_change()
        return True


def _entry_minutes(e: storage.WorkEntry) -> int:
    return entry_minutes(e.time_in, e.time_out)
