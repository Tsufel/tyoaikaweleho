"""Timer card: elapsed/earnings display and start/stop controls."""
from datetime import date, datetime, timedelta

import customtkinter as ctk

import storage
import timer as timer_module
from utils import (resolve_start_time, start_time_needs_confirm, is_long_shift,
                   format_duration, MIN_SHIFT_SECONDS)
from ui import msgbox as messagebox
from ui import theme
from ui.time_picker_popup import TimePickerPopup

_IDLE_TEXT = "Press START (F5) to begin tracking"
_MAX_ENTRY_MINUTES = 24 * 60


class TimerPanel(ctk.CTkFrame):
    """The timer card at the top of the main window.

    on_entry_saved(entry) is called after a stopped shift has been written
    to storage, so the parent can show it in the entries table.
    on_status(msg) shows a short note, e.g. when a mis-click start is dropped.
    """

    def __init__(self, master, on_entry_saved, on_status=None):
        super().__init__(master, corner_radius=12)
        self._timer = timer_module.WorkTimer()
        self._on_entry_saved = on_entry_saved
        self._on_status = on_status or (lambda _msg: None)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(pady=14)

        self._elapsed_label = ctk.CTkLabel(
            inner, text="00:00",
            font=ctk.CTkFont(size=46, weight="bold"))
        self._elapsed_label.pack()

        self._earnings_label = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(size=13), text_color=theme.TEXT_SUCCESS)
        self._earnings_label.pack(pady=(0, 2))

        self._start_time_label = ctk.CTkLabel(
            inner, text=_IDLE_TEXT,
            font=ctk.CTkFont(size=11), text_color=theme.TEXT_MUTED)
        self._start_time_label.pack(pady=(0, 8))

        # Job picker — only while idle; once running, the label names the job
        self._job_row = ctk.CTkFrame(inner, fg_color="transparent")
        ctk.CTkLabel(self._job_row, text="Job / shift",
                     font=ctk.CTkFont(size=12),
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        self._job_var = ctk.StringVar(value=storage.get_default_job_shift())
        self._job_combo = ctk.CTkComboBox(self._job_row, variable=self._job_var,
                                          values=_job_list(), width=200)
        self._job_combo.pack(side="left")

        # Button slot — holds either the start buttons or the stop button
        self._btn_slot = ctk.CTkFrame(inner, fg_color="transparent")
        self._btn_slot.pack(pady=(0, 4))

        self._btn_row = ctk.CTkFrame(self._btn_slot, fg_color="transparent")
        self._btn_row.pack()

        self._start_now_btn = ctk.CTkButton(
            self._btn_row, text="▶  START NOW", width=170, height=52,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
            command=lambda: self.start(start_time=None))
        self._start_now_btn.pack(side="left", padx=(0, 6))

        self._start_at_btn = ctk.CTkButton(
            self._btn_row,
            text=f"⏰  {storage.get_default_start_time()}", width=110, height=52,
            font=ctk.CTkFont(size=12),
            fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
            command=self._start_at_default)
        self._start_at_btn.pack(side="left")
        self._start_at_btn.bind("<Button-3>", lambda _e: self._pick_start_time())

        self._pick_btn = ctk.CTkButton(
            self._btn_row, text="▾", width=30, height=52,
            font=ctk.CTkFont(size=14),
            fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
            command=self._pick_start_time)
        self._pick_btn.pack(side="left", padx=(2, 0))

        self._stop_btn = ctk.CTkButton(
            self._btn_slot, text="⏹   STOP SHIFT", width=318, height=52,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=theme.RED, hover_color=theme.RED_HOVER,
            command=self.stop)

        self._idle_ui()
        self._tick()

    # ── Public API ───────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._timer.is_running

    def elapsed_seconds(self) -> float:
        return self._timer.elapsed_seconds()

    def start_time_str(self) -> str:
        return self._timer.start_time_str()

    def toggle(self):
        """F5: start now, or — after asking — stop."""
        if not self.is_running:
            self.start(start_time=None)
            return
        minutes = int(self._timer.elapsed_seconds() // 60)
        long = is_long_shift(minutes)
        if messagebox.askyesno(
                "Stop shift?",
                f"Stop the shift started at {self._timer.start_time_str()} "
                f"({format_duration(minutes)} ago) and save it?",
                icon="warning" if long else "question", parent=self):
            self.stop(confirm=False)

    def start(self, start_time: datetime | None, job_shift: str | None = None):
        if self.is_running:
            return
        js = (job_shift or self._job_var.get() or storage.get_default_job_shift()).strip()
        self._timer.start(js or "—", start_time=start_time)
        self._running_ui()
        self._update_labels()

    def stop(self, confirm: bool = True) -> bool:
        """Stop and save the running shift. Returns False (and keeps the
        shift running) if the user backs out of the long-shift question or
        the entry could not be written."""
        if not self.is_running:
            return True
        start_dt, job_shift = self._timer.start_dt, self._timer.job_shift
        elapsed = self._timer.elapsed_seconds()
        if elapsed < MIN_SHIFT_SECONDS:
            # a start and stop within a minute is a mis-click, not a shift
            self._timer.stop()
            timer_module.clear_saved_session()
            self._reset()
            self._on_status("Shift under a minute — not saved")
            return True
        minutes = int(elapsed // 60)
        time_out = None
        if minutes >= _MAX_ENTRY_MINUTES:
            # An entry holds under a day: saved as is, 25 h would keep only
            # the leftover 1 h. Offer the 8-hour mark, like crash recovery.
            capped = start_dt + timedelta(hours=8)
            choice = messagebox.askchoice(
                "Shift over 24 hours",
                f"This shift has been running for {format_duration(minutes)} "
                f"(since {start_dt:%a %d %b %H:%M}), longer than one entry "
                f"can hold.\n\nSave it ending at the 8-hour mark "
                f"({capped:%H:%M}) and fix the end time in the table, "
                "or discard it?",
                [("save", f"Save until {capped:%H:%M}"),
                 ("discard", "Discard", "danger"),
                 ("keep", "Keep running")],
                default="keep", cancel="keep", icon="warning", parent=self)
            if choice == "discard" and messagebox.askyesno(
                    "Discard shift", "Discard this shift? It will not be saved.",
                    icon="warning", parent=self):
                self._timer.stop()
                timer_module.clear_saved_session()
                self._reset()
                self._on_status("Shift discarded")
                return True
            if choice != "save":
                return False
            time_out = f"{capped:%H:%M}"
        elif confirm and is_long_shift(minutes) and not messagebox.askyesno(
                "Long shift",
                f"This shift has been running for {format_duration(minutes)} "
                f"(since {start_dt:%a %d %b %H:%M}).\n\nStop and save it?\n\n"
                "No keeps the timer running.",
                icon="warning", parent=self):
            return False

        result = self._timer.stop()
        if time_out is not None:
            result["time_out"] = time_out
        entry = storage.WorkEntry(id=storage.new_entry_id(), **result)
        try:
            storage.save_entry(entry)
        except OSError as exc:
            # Keep the shift running (session.json is still on disk) so
            # nothing is lost and the user can retry
            self._timer.start(job_shift, start_time=start_dt)
            messagebox.showerror(
                "Could not save shift",
                "The shift could not be saved and is still running.\n\n"
                f"{exc}\n\nClose any program that may be locking "
                "data.json and press STOP again.",
                parent=self)
            return False
        timer_module.clear_saved_session()
        self._reset()
        self._on_entry_saved(entry)
        return True

    def refresh_settings(self):
        """Re-read settings that affect this panel (default start time and
        job, shift list)."""
        self._start_at_btn.configure(text=f"⏰  {storage.get_default_start_time()}")
        self._job_combo.configure(values=_job_list())
        if not self.is_running:
            self._job_var.set(storage.get_default_job_shift())

    # ── Internals ────────────────────────────────────────────────

    def _start_at(self, t: str):
        h, m = map(int, t.split(":"))
        now = datetime.now()
        if not start_time_needs_confirm(h, m, now):
            self.start(resolve_start_time(h, m, now))
            return
        # A time a little later than now is more likely "I'm starting about
        # now" than a shift that began nearly a day ago — ask
        earlier = resolve_start_time(h, m, now)
        # usually yesterday; today when the next HH:MM is after midnight
        day = "today" if earlier.date() == now.date() else "yesterday"
        choice = messagebox.askchoice(
            "Start time hasn't come yet",
            f"It's {now:%H:%M} now, so the next {t} is still ahead.\n\n"
            f"Start the shift now, or from {t} {day} ({earlier:%a %d %b})?",
            [("now", f"Start now ({now:%H:%M})"),
             ("yesterday", f"From {day} {t}"),
             ("cancel", "Cancel")],
            default="now", cancel="cancel", parent=self)
        if choice == "now":
            self.start(start_time=None)
        elif choice == "yesterday":
            self.start(earlier)

    def _start_at_default(self):
        self._start_at(storage.get_default_start_time())

    def _pick_start_time(self):
        if self.is_running:
            return
        popup = TimePickerPopup(self, initial=storage.get_default_start_time(),
                                anchor_widget=self._start_at_btn)
        self.wait_window(popup)
        if popup.result:
            self._start_at(popup.result)

    def _idle_ui(self):
        self._stop_btn.pack_forget()
        self._job_row.pack(before=self._btn_slot, pady=(0, 8))
        self._btn_row.pack()

    def _running_ui(self):
        self._btn_row.pack_forget()
        self._job_row.pack_forget()
        self._stop_btn.pack(fill="x")

    def _reset(self):
        self._idle_ui()
        self._elapsed_label.configure(text="00:00")
        self._earnings_label.configure(text="")
        self._start_time_label.configure(text=_IDLE_TEXT, text_color=theme.TEXT_MUTED)

    def _running_text(self) -> str:
        start = self._timer.start_dt
        text = f"Started {start:%H:%M}"
        days = (date.today() - start.date()).days
        if days == 1:
            text += " (yesterday)"
        elif days:
            text += f" ({start:%a %d %b})"
        return f"{text}  ·  {self._timer.job_shift}  ·  running…"

    def _update_labels(self):
        if self._timer.is_running:
            self._elapsed_label.configure(text=self._timer.elapsed_str())
            rate = storage.get_pay_rate()
            earned = self._timer.elapsed_seconds() / 3600 * rate
            self._earnings_label.configure(text=f"~€{earned:.2f} earned so far")
            # re-rendered every tick: "today" becomes "yesterday" at midnight
            self._start_time_label.configure(text=self._running_text(),
                                             text_color=theme.TEXT_WARNING)

    def _tick(self):
        # Single repeating loop scheduled once at construction — start()
        # only updates labels immediately rather than spawning another loop.
        # Rescheduled first so an error in one update can't stop the clock.
        self.after(60_000, self._tick)
        self._update_labels()


def _job_list() -> list[str]:
    try:
        return storage.get_job_shift_list()
    except OSError:
        return []
