"""Timer card: elapsed/earnings display and start/stop controls."""
from datetime import datetime

import customtkinter as ctk

import storage
import timer as timer_module
from ui import theme


class TimerPanel(ctk.CTkFrame):
    """The timer card at the top of the main window.

    on_entry_saved() is called after a stopped shift has been written
    to storage, so the parent can refresh the entries table.
    """

    def __init__(self, master, on_entry_saved):
        super().__init__(master, corner_radius=12)
        self._timer = timer_module.WorkTimer()
        self._on_entry_saved = on_entry_saved

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(pady=14)

        self._elapsed_label = ctk.CTkLabel(
            inner, text="00:00",
            font=ctk.CTkFont(size=46, weight="bold"))
        self._elapsed_label.pack()

        self._earnings_label = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(size=13), text_color=theme.GREEN)
        self._earnings_label.pack(pady=(0, 2))

        self._start_time_label = ctk.CTkLabel(
            inner, text="Press START to begin tracking",
            font=ctk.CTkFont(size=11), text_color=theme.GRAY)
        self._start_time_label.pack(pady=(0, 10))

        # Button slot — holds either two start buttons or the stop button
        _btn_slot = ctk.CTkFrame(inner, fg_color="transparent")
        _btn_slot.pack(pady=(0, 4))

        self._btn_row = ctk.CTkFrame(_btn_slot, fg_color="transparent")
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
            fg_color="#555555", hover_color="#333333",
            command=self._start_at_default)
        self._start_at_btn.pack(side="left")

        self._stop_btn = ctk.CTkButton(
            _btn_slot, text="⏹   STOP SHIFT", width=286, height=52,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=theme.RED, hover_color=theme.RED_HOVER,
            command=self.stop)
        # _stop_btn starts hidden; shown by _running_ui()

        self._tick()

    # ── Public API ───────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._timer.is_running

    def toggle(self):
        if self.is_running:
            self.stop()
        else:
            self.start(start_time=None)

    def start(self, start_time: datetime | None, job_shift: str | None = None):
        js = (job_shift or storage.get_default_job_shift() or "—").strip()
        self._timer.start(js, start_time=start_time)
        self._running_ui()
        self._start_time_label.configure(
            text=f"Started at {self._timer.start_time_str()}  —  running…",
            text_color=theme.ORANGE)
        self._update_labels()

    def stop(self):
        result = self._timer.stop()
        if result:
            storage.save_entry(storage.WorkEntry(
                id=storage.new_entry_id(),
                date=result["date"],
                job_shift=result["job_shift"],
                time_in=result["time_in"],
                time_out=result["time_out"],
            ))
            self._on_entry_saved()
        self._idle_ui()
        self._elapsed_label.configure(text="00:00")
        self._earnings_label.configure(text="")
        self._start_time_label.configure(
            text="Press START to begin tracking", text_color=theme.GRAY)

    def refresh_settings(self):
        """Re-read settings that affect this panel (default start time)."""
        self._start_at_btn.configure(text=f"⏰  {storage.get_default_start_time()}")

    # ── Internals ────────────────────────────────────────────────

    def _start_at_default(self):
        t = storage.get_default_start_time()
        h, m = map(int, t.split(":"))
        self.start(datetime.now().replace(hour=h, minute=m, second=0, microsecond=0))

    def _idle_ui(self):
        self._stop_btn.pack_forget()
        self._btn_row.pack()

    def _running_ui(self):
        self._btn_row.pack_forget()
        self._stop_btn.pack(fill="x")

    def _update_labels(self):
        if self._timer.is_running:
            self._elapsed_label.configure(text=self._timer.elapsed_str())
            rate = storage.get_pay_rate()
            earned = self._timer.elapsed_seconds() / 3600 * rate
            self._earnings_label.configure(text=f"~€{earned:.2f} earned so far")

    def _tick(self):
        # Single repeating loop scheduled once at construction — start()
        # only updates labels immediately rather than spawning another loop
        self._update_labels()
        self.after(60_000, self._tick)
