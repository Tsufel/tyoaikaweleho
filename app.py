import os
import sys
import subprocess
import tkinter as tk
import urllib.request
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta

import storage
import timer as timer_module
import excel_export
import import_excel

try:
    import image_ocr as _image_ocr_dlc   # optional OCR DLC — loaded when image_ocr.py is present
except ImportError:
    _image_ocr_dlc = None


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

_GREEN = "#27ae60"
_GREEN_HOVER = "#1e8449"
_RED = "#c0392b"
_RED_HOVER = "#922b21"
_GRAY = "#7f8c8d"

_MONTHS = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


from utils import parse_time_input as _parse_time_input
from utils import is_valid_time    as _is_valid_time
from utils import get_app_dir      as _get_app_dir


class MonthPickerDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_year: int, current_month: int):
        super().__init__(parent)
        self.title("Jump to month")
        self.geometry("260x150")
        self.resizable(False, False)
        self.grab_set()
        self.result: tuple[int, int] | None = None

        ctk.CTkLabel(self, text="Month").pack(pady=(14, 2))
        self._month_var = ctk.StringVar(value=_MONTHS[current_month - 1])
        ctk.CTkOptionMenu(self, variable=self._month_var,
                          values=_MONTHS, width=220).pack()

        ctk.CTkLabel(self, text="Year").pack(pady=(8, 2))
        self._year_var = ctk.StringVar(value=str(current_year))
        ctk.CTkEntry(self, textvariable=self._year_var, width=220).pack()

        ctk.CTkButton(self, text="Go", width=220, height=34,
                      command=self._go).pack(pady=10)

    def _go(self):
        try:
            year = int(self._year_var.get().strip())
            month = _MONTHS.index(self._month_var.get()) + 1
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
                      fg_color=_GREEN, hover_color=_GREEN_HOVER,
                      command=self._save).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Cancel", width=130,
                      fg_color=_GRAY, hover_color="#636e72",
                      command=self.destroy).pack(side="left", padx=8)

    def _save(self):
        d = self._date_var.get().strip()
        try:
            date.fromisoformat(d)
        except ValueError:
            messagebox.showerror("Invalid date", "Enter date as YYYY-MM-DD", parent=self)
            return
        t_in = _parse_time_input(self._time_in_var.get())
        t_out_raw = self._time_out_var.get().strip()
        t_out = _parse_time_input(t_out_raw) if t_out_raw else ""
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


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("320x520")
        self.resizable(False, False)
        self.grab_set()
        self.changed = False

        pad = {"padx": 24, "pady": (8, 2)}

        # ── Timer ──────────────────────────────────────────────
        ctk.CTkLabel(self, text="Default start time",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._start_time_var = ctk.StringVar(value=storage.get_default_start_time())
        ctk.CTkEntry(self, textvariable=self._start_time_var, width=272).pack(padx=24)

        ctk.CTkLabel(self, text="Pay rate (€/hr)",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._pay_rate_var = ctk.StringVar(value=str(storage.get_pay_rate()))
        ctk.CTkEntry(self, textvariable=self._pay_rate_var, width=272).pack(padx=24)

        # ── Job / Shift ────────────────────────────────────────
        ctk.CTkLabel(self, text="Default job / shift",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._job_var = ctk.StringVar(value=storage.get_default_job_shift())
        self._job_combo = ctk.CTkComboBox(self, variable=self._job_var,
                              values=storage.get_job_shift_list(), width=272)
        self._job_combo.pack(padx=24)

        add_row = ctk.CTkFrame(self, fg_color="transparent")
        add_row.pack(padx=24, pady=(4, 0), fill="x")
        self._new_shift_var = ctk.StringVar()
        _shift_entry = ctk.CTkEntry(add_row, textvariable=self._new_shift_var,
                                    placeholder_text="Add new shift…", width=206)
        _shift_entry.pack(side="left")
        _shift_entry.bind("<Return>", lambda _e: self._add_shift())
        ctk.CTkButton(add_row, text="+ Add", width=62,
                      fg_color=_GREEN, hover_color=_GREEN_HOVER,
                      command=self._add_shift).pack(side="left", padx=(4, 0))

        ctk.CTkButton(self, text="Edit shifts.txt  →", width=272,
                      fg_color="#2c3e50", hover_color="#1a252f",
                      command=lambda: os.startfile(storage.SHIFTS_FILE)).pack(
                          padx=24, pady=(4, 0))

        # ── Output ────────────────────────────────────────────
        ctk.CTkLabel(self, text="Output",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._fmt_var = ctk.StringVar(value=storage.get_export_format())
        ctk.CTkOptionMenu(self, variable=self._fmt_var,
                          values=["Simple", "Full"],
                          width=272).pack(padx=24)
        self._pay_chk_var = ctk.BooleanVar(value=storage.get_export_include_pay())
        ctk.CTkCheckBox(self, text="Include total pay in export",
                        variable=self._pay_chk_var).pack(
                            padx=24, pady=(6, 0), anchor="w")

        # ── DLC Store ──────────────────────────────────────────
        ctk.CTkLabel(self, text="DLC Store",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        if _image_ocr_dlc is not None:
            ctk.CTkLabel(self, text="✅  Image OCR — installed",
                         text_color="#27ae60").pack(padx=24, pady=(0, 6), anchor="w")
        else:
            ctk.CTkButton(self, text="⬇  Install Image OCR", width=272,
                          fg_color="#6c3483", hover_color="#512e5f",
                          command=self._install_image_ocr).pack(padx=24, pady=(2, 6))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=(8, 16))
        ctk.CTkButton(row, text="Save", width=120,
                      fg_color=_GREEN, hover_color=_GREEN_HOVER,
                      command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Cancel", width=120,
                      fg_color=_GRAY, hover_color="#636e72",
                      command=self.destroy).pack(side="left", padx=6)

    def _add_shift(self):
        js = self._new_shift_var.get().strip()
        if not js:
            return
        if storage.add_job_shift(js):
            self._job_combo.configure(values=storage.get_job_shift_list())
            self._job_var.set(js)
            self._new_shift_var.set("")
        else:
            messagebox.showinfo("Already exists",
                                f"'{js}' is already in the shift list.", parent=self)

    def _install_image_ocr(self):
        try:
            from version import GITHUB_REPO
        except ImportError:
            GITHUB_REPO = ""
        if not GITHUB_REPO or "YOUR_GITHUB_USERNAME" in GITHUB_REPO:
            messagebox.showerror(
                "Not configured",
                "The GitHub repository hasn't been set up yet.\n"
                "Update GITHUB_REPO in version.py first.",
                parent=self)
            return

        url  = f"https://raw.githubusercontent.com/{GITHUB_REPO}/dlc/image_ocr.py"
        # When frozen the DLC must live next to the .exe; otherwise next to the .py
        dest = os.path.join(
            os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)),
            "image_ocr.py",
        )

        prog = ctk.CTkToplevel(self)
        prog.title("Installing DLC")
        prog.geometry("360x110")
        prog.resizable(False, False)
        prog.grab_set()
        lbl = ctk.CTkLabel(prog, text="Downloading image_ocr.py…")
        lbl.pack(pady=(24, 6))
        bar = ctk.CTkProgressBar(prog, mode="indeterminate")
        bar.pack(padx=30, fill="x")
        bar.start()
        prog.update()

        try:
            urllib.request.urlretrieve(url, dest)
            bar.stop()
            prog.destroy()
            messagebox.showinfo(
                "DLC installed",
                "Image OCR DLC installed! ✅\n\n"
                "Restart the app to activate the 📷 Import from Image button.\n\n"
                "Uses Windows built-in OCR — no extra software needed.\n"
                "For best results with Finnish timesheets, ensure Finnish\n"
                "is added in Windows Settings → Language.",
                parent=self)
            self.changed = True
            self.destroy()
        except Exception as exc:
            bar.stop()
            prog.destroy()
            messagebox.showerror("Install failed", str(exc), parent=self)

    def _save(self):
        t = _parse_time_input(self._start_time_var.get())
        if t is None:
            messagebox.showerror("Invalid time",
                                 "Default start time must be a valid time (e.g. 09:30).",
                                 parent=self)
            return
        try:
            rate = float(self._pay_rate_var.get().replace(",", "."))
            if rate <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid rate",
                                 "Pay rate must be a positive number.", parent=self)
            return
        storage.set_default_start_time(t)
        storage.set_pay_rate(rate)
        storage.set_default_job_shift(self._job_var.get().strip())
        storage.set_export_format(self._fmt_var.get())
        storage.set_export_include_pay(self._pay_chk_var.get())
        self.changed = True
        self.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Työaikaweleho")
        self.geometry("860x700")
        self.minsize(700, 560)
        self.withdraw()  # hidden until splash finishes

        self._timer = timer_module.WorkTimer()
        today = date.today()
        self._view_year = today.year
        self._view_month = today.month

        self._setup_table_style()
        self._build_ui()
        self._refresh_table()
        self._tick()
        self.bind("<F5>", lambda _e: self._stop_timer() if self._timer.is_running else self._start_timer(None))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_icon()
        # Splash reveals the main window and triggers crash recovery when done
        self.after(50, self._show_splash)
        # Background update check (silently ignored if network unavailable)
        try:
            from version import __version__
            import updater as _updater_mod
            _updater_mod.check_for_update(__version__, self._on_update_available)
        except Exception:
            pass

    # ── Icon & splash ─────────────────────────────────────────────

    def _setup_icon(self):
        """Set window/taskbar icon from icon.ico (preferred) or toolbar.png."""
        app_dir = _get_app_dir()
        ico_path = os.path.join(app_dir, "icon.ico")
        png_path = os.path.join(app_dir, "toolbar.png")
        try:
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
            elif os.path.exists(png_path):
                from PIL import Image, ImageTk
                img = Image.open(png_path).resize((64, 64), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._icon_photo = photo  # keep reference to prevent GC
                self.iconphoto(True, photo)
        except Exception:
            pass

    def _show_splash(self):
        """Show splash.png for 2.5 s, then reveal the main window and run crash recovery."""
        png_path = os.path.join(_get_app_dir(), "splash.png")

        def _finish():
            self.deiconify()
            self.lift()
            self.after(100, self._check_for_crash_recovery)

        if not os.path.exists(png_path):
            _finish()
            return

        try:
            from PIL import Image, ImageTk
            size = 500
            img = Image.open(png_path).resize((size, size), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            splash = tk.Toplevel(self)
            splash.overrideredirect(True)   # borderless window
            splash.resizable(False, False)
            splash._photo = photo           # prevent GC

            tk.Label(splash, image=photo, bd=0).pack()

            sw = splash.winfo_screenwidth()
            sh = splash.winfo_screenheight()
            splash.geometry(f"{size}x{size}+{(sw - size) // 2}+{(sh - size) // 2}")
            splash.lift()
            splash.after(2500, lambda: (splash.destroy(), _finish()))

        except Exception:
            _finish()

    # ── Table style ──────────────────────────────────────────────

    def _setup_table_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        rowheight=28,
                        font=("Arial", 10),
                        background="#2b2b2b" if self._is_dark() else "#ffffff",
                        foreground="white" if self._is_dark() else "black",
                        fieldbackground="#2b2b2b" if self._is_dark() else "#ffffff")
        style.configure("Treeview.Heading",
                        font=("Arial", 10, "bold"),
                        background="#1f538d" if self._is_dark() else "#3b8ed0",
                        foreground="white")
        style.map("Treeview",
                  background=[("selected", "#1f538d")],
                  foreground=[("selected", "white")])

    def _is_dark(self) -> bool:
        return ctk.get_appearance_mode().lower() == "dark"

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self):
        # ── Top bar ──────────────────────────────────────────────
        top = ctk.CTkFrame(self, height=52, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        nav = ctk.CTkFrame(top, fg_color="transparent")
        nav.pack(side="left", padx=12, pady=8)
        ctk.CTkButton(nav, text="◄", width=34, height=34,
                      command=self._prev_month).pack(side="left")

        self._month_label = ctk.CTkLabel(
            nav, text="", width=180, cursor="hand2",
            font=ctk.CTkFont(size=15, weight="bold"))
        self._month_label.pack(side="left", padx=6)
        self._month_label.bind("<Button-1>", lambda _e: self._open_month_picker())

        ctk.CTkButton(nav, text="►", width=34, height=34,
                      command=self._next_month).pack(side="left")

        ctk.CTkButton(top, text="Import from Excel…", width=160,
                      fg_color=_GRAY, hover_color="#636e72",
                      command=self._import_excel).pack(side="right", padx=12, pady=8)
        if _image_ocr_dlc is not None:
            ctk.CTkButton(top, text="📷  Import from Image…", width=190,
                          fg_color="#6c3483", hover_color="#512e5f",
                          command=self._import_image).pack(side="right", padx=(0, 6), pady=8)
        ctk.CTkButton(top, text="⚙  Settings", width=110,
                      fg_color="#2c3e50", hover_color="#1a252f",
                      command=self._open_settings).pack(side="right", padx=(0, 6), pady=8)

        # ── Timer card ───────────────────────────────────────────
        timer_card = ctk.CTkFrame(self, corner_radius=12)
        timer_card.pack(fill="x", padx=16, pady=(10, 0))

        inner = ctk.CTkFrame(timer_card, fg_color="transparent")
        inner.pack(pady=14)

        self._elapsed_label = ctk.CTkLabel(
            inner, text="00:00",
            font=ctk.CTkFont(size=46, weight="bold"))
        self._elapsed_label.pack()

        self._earnings_label = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(size=13), text_color="#27ae60")
        self._earnings_label.pack(pady=(0, 2))

        self._start_time_label = ctk.CTkLabel(
            inner, text="Press START to begin tracking",
            font=ctk.CTkFont(size=11), text_color=_GRAY)
        self._start_time_label.pack(pady=(0, 10))

        # Button slot — holds either two start buttons or the stop button
        _btn_slot = ctk.CTkFrame(inner, fg_color="transparent")
        _btn_slot.pack(pady=(0, 4))

        self._btn_row = ctk.CTkFrame(_btn_slot, fg_color="transparent")
        self._btn_row.pack()

        self._start_now_btn = ctk.CTkButton(
            self._btn_row, text="▶  START NOW", width=170, height=52,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_GREEN, hover_color=_GREEN_HOVER,
            command=lambda: self._start_timer(start_time=None))
        self._start_now_btn.pack(side="left", padx=(0, 6))

        self._start_at_btn = ctk.CTkButton(
            self._btn_row,
            text=f"⏰  {storage.get_default_start_time()}", width=110, height=52,
            font=ctk.CTkFont(size=12),
            fg_color="#555555", hover_color="#333333",
            command=self._start_at_dialog)
        self._start_at_btn.pack(side="left")

        self._stop_btn = ctk.CTkButton(
            _btn_slot, text="⏹   STOP SHIFT", width=286, height=52,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=_RED, hover_color=_RED_HOVER,
            command=self._stop_timer)
        # _stop_btn starts hidden; shown by _running_ui()


        # ── Entries section ──────────────────────────────────────
        entries_header = ctk.CTkFrame(self, fg_color="transparent")
        entries_header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(entries_header, text="Shifts this month",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(entries_header, text="+ Add entry manually",
                      width=160, height=30,
                      command=self._add_manual).pack(side="right")

        # ── Table ────────────────────────────────────────────────
        table_frame = ctk.CTkFrame(self, corner_radius=8)
        table_frame.pack(fill="both", expand=True, padx=16)

        cols = ("date", "shift", "time_in", "time_out", "hours")
        self._tree = ttk.Treeview(table_frame, columns=cols, show="headings",
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

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y", pady=2)

        self._tree.bind("<Double-1>", lambda _e: self._edit_selected())
        self._tree.bind("<ButtonRelease-1>", self._on_cell_click)
        self._inline_editor: tk.Entry | None = None

        # ── Bottom bar ───────────────────────────────────────────
        bottom = ctk.CTkFrame(self, height=52, corner_radius=0)
        bottom.pack(fill="x", pady=(4, 0))
        bottom.pack_propagate(False)

        ctk.CTkButton(bottom, text="✏  Edit", width=100, height=34,
                      fg_color=_GRAY, hover_color="#636e72",
                      command=self._edit_selected).pack(side="left", padx=(12, 4), pady=9)
        ctk.CTkButton(bottom, text="🗑  Delete", width=100, height=34,
                      fg_color=_RED, hover_color=_RED_HOVER,
                      command=self._delete_selected).pack(side="left", padx=4, pady=9)

        self._total_label = ctk.CTkLabel(
            bottom, text="Total: 0:00",
            font=ctk.CTkFont(size=13, weight="bold"))
        self._total_label.pack(side="left", padx=20)

        ctk.CTkButton(bottom, text="Export to Excel  →", width=160, height=34,
                      fg_color="#1f538d",
                      command=self._export_excel).pack(side="right", padx=12, pady=9)

        self._update_month_label()

    # ── Crash recovery ────────────────────────────────────────────

    def _check_for_crash_recovery(self):
        session = timer_module.load_saved_session()
        if not session:
            return
        try:
            start_dt = datetime.fromisoformat(session["start"])
        except Exception:
            timer_module.clear_saved_session()
            return

        job_shift = session.get("job_shift", "?")
        date_str  = start_dt.strftime("%Y-%m-%d")
        elapsed   = datetime.now() - start_dt
        elapsed_h = elapsed.total_seconds() / 3600

        # ── Auto-end if over 8 hours ──────────────────────────────
        if elapsed_h >= 8:
            auto_end = start_dt + timedelta(hours=8)
            storage.save_entry(storage.WorkEntry(
                id=storage.new_entry_id(),
                date=date_str,
                job_shift=job_shift,
                time_in=start_dt.strftime("%H:%M"),
                time_out=auto_end.strftime("%H:%M"),
            ))
            timer_module.clear_saved_session()
            self._view_year  = start_dt.year
            self._view_month = start_dt.month
            self._refresh_table()
            messagebox.showinfo(
                "Shift auto-ended",
                f"A shift started at {start_dt.strftime('%H:%M')} was automatically\n"
                f"ended at {auto_end.strftime('%H:%M')} (8-hour limit).",
                parent=self)
            return

        # ── Under 8 h — let the user decide ──────────────────────
        h = int(elapsed.total_seconds() // 3600)
        m = int((elapsed.total_seconds() % 3600) // 60)
        now_str = datetime.now().strftime("%H:%M")
        msg = (
            f"An unfinished shift was found:\n\n"
            f"  Date:      {date_str}\n"
            f"  Job/Shift: {job_shift}\n"
            f"  Started:   {start_dt.strftime('%H:%M')}\n"
            f"  Elapsed:   {h}h {m:02d}m\n\n"
            f"Yes    →  Resume the shift\n"
            f"No     →  Save with end time {now_str}\n"
            f"Cancel →  Discard"
        )
        answer = messagebox.askyesnocancel("Recover shift", msg, parent=self)

        if answer is True:      # Resume
            self._start_timer(start_time=start_dt, job_shift=job_shift)
            self._view_year  = start_dt.year
            self._view_month = start_dt.month
            self._refresh_table()

        elif answer is False:   # Save with end time now
            storage.save_entry(storage.WorkEntry(
                id=storage.new_entry_id(),
                date=date_str,
                job_shift=job_shift,
                time_in=start_dt.strftime("%H:%M"),
                time_out=now_str,
            ))
            timer_module.clear_saved_session()
            self._view_year  = start_dt.year
            self._view_month = start_dt.month
            self._refresh_table()

        else:                   # Discard
            timer_module.clear_saved_session()

    # ── Close handler ────────────────────────────────────────────

    def _on_close(self):
        if not self._timer.is_running:
            self.destroy()
            return
        answer = messagebox.askyesnocancel(
            "Shift still running",
            "A shift is currently running.\n\n"
            "Yes  →  Stop the shift, save it, then close\n"
            "No   →  Close anyway (shift will be recovered on next open)\n"
            "Cancel  →  Stay open",
            parent=self,
        )
        if answer is True:
            self._stop_timer()
            self.destroy()
        elif answer is False:
            self.destroy()
        # answer is None (Cancel) → do nothing

    # ── Timer ────────────────────────────────────────────────────

    def _idle_ui(self):
        self._stop_btn.pack_forget()
        self._btn_row.pack()

    def _running_ui(self):
        self._btn_row.pack_forget()
        self._stop_btn.pack(fill="x")

    def _tick(self):
        if self._timer.is_running:
            self._elapsed_label.configure(text=self._timer.elapsed_str())
            rate = storage.get_pay_rate()
            earned = self._timer.elapsed_seconds() / 3600 * rate
            self._earnings_label.configure(text=f"~€{earned:.2f} earned so far")
        self.after(60_000, self._tick)

    def _start_timer(self, start_time: datetime | None, job_shift: str | None = None):
        js = (job_shift or storage.get_default_job_shift() or "—").strip()
        self._timer.start(js, start_time=start_time)
        self._running_ui()
        self._start_time_label.configure(
            text=f"Started at {self._timer.start_time_str()}  —  running…",
            text_color="#e67e22")
        self._tick()

    def _stop_timer(self):
        result = self._timer.stop()
        if result:
            entry = storage.WorkEntry(
                id=storage.new_entry_id(),
                date=result["date"],
                job_shift=result["job_shift"],
                time_in=result["time_in"],
                time_out=result["time_out"],
            )
            storage.save_entry(entry)
            self._refresh_table()
        self._idle_ui()
        self._elapsed_label.configure(text="00:00")
        self._earnings_label.configure(text="")
        self._start_time_label.configure(
            text="Press START to begin tracking", text_color=_GRAY)

    def _start_at_dialog(self):
        t = storage.get_default_start_time()
        h, m = map(int, t.split(":"))
        self._start_timer(datetime.now().replace(hour=h, minute=m, second=0, microsecond=0))

    # ── Auto-update ──────────────────────────────────────────────

    def _on_update_available(self, new_ver: str, url: str):
        # Called from a background thread — marshal to UI thread
        self.after(0, lambda: self._show_update_dialog(new_ver, url))

    def _show_update_dialog(self, new_ver: str, url: str):
        try:
            from version import __version__
            current = __version__
        except Exception:
            current = "unknown"
        if messagebox.askyesno(
            "Update available",
            f"Version {new_ver} is available (you have {current}).\n\n"
            "Download and install now?\n\n"
            "(The app will close and relaunch automatically.)",
            parent=self,
        ):
            import updater as _updater_mod
            _updater_mod.apply_update(url)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        self.wait_window(dlg)
        if dlg.changed:
            self._start_at_btn.configure(text=f"⏰  {storage.get_default_start_time()}")
            self._refresh_table()

    # ── Table ────────────────────────────────────────────────────

    def _refresh_table(self):
        for row in self._tree.get_children():
            self._tree.delete(row)

        entries = storage.load_month(self._view_year, self._view_month)

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
                    mins = self._entry_minutes(e)
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

        th, tm = divmod(total_minutes, 60)
        earnings = total_minutes / 60 * rate
        self._total_label.configure(
            text=f"Total: {th}:{tm:02d}  (€{earnings:.2f})")
        self._update_month_label()

    def _entry_minutes(self, e: storage.WorkEntry) -> int:
        try:
            ih, im = map(int, e.time_in.split(":"))
            oh, om = map(int, e.time_out.split(":"))
            return max(0, (oh * 60 + om) - (ih * 60 + im))
        except Exception:
            return 0

    # ── Month navigation ─────────────────────────────────────────

    def _prev_month(self):
        if self._view_month == 1:
            self._view_month, self._view_year = 12, self._view_year - 1
        else:
            self._view_month -= 1
        self._refresh_table()

    def _next_month(self):
        if self._view_month == 12:
            self._view_month, self._view_year = 1, self._view_year + 1
        else:
            self._view_month += 1
        self._refresh_table()

    def _update_month_label(self):
        name = date(self._view_year, self._view_month, 1).strftime("%B %Y")
        self._month_label.configure(text=f"{name} ▾")

    def _open_month_picker(self):
        dlg = MonthPickerDialog(self, self._view_year, self._view_month)
        self.wait_window(dlg)
        if dlg.result:
            self._view_year, self._view_month = dlg.result
            self._refresh_table()

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
            parsed = _parse_time_input(new_val)
            if parsed is None or parsed == current:
                self._refresh_table()
                return
            all_entries = storage.load_all_entries()
            entry = next((en for en in all_entries if en.id == row_id), None)
            if entry:
                setattr(entry, field, parsed)
                storage.update_entry(entry)
            self._refresh_table()

        def cancel(e=None):
            self._inline_editor = None
            editor.destroy()

        editor.bind("<Return>", commit)
        editor.bind("<Tab>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", cancel)

    # ── Entry actions ────────────────────────────────────────────

    def _add_manual(self):
        dlg = EditEntryDialog(
            self, default_date=date(self._view_year, self._view_month, 1))
        self.wait_window(dlg)
        if dlg.result:
            storage.save_entry(dlg.result)
            self._refresh_table()

    def _edit_selected(self):
        sel = self._tree.selection()
        if not sel or sel[0].startswith("week_"):
            return
        all_entries = storage.load_all_entries()
        entry = next((e for e in all_entries if e.id == sel[0]), None)
        if not entry:
            return
        dlg = EditEntryDialog(self, entry=entry)
        self.wait_window(dlg)
        if dlg.result:
            storage.update_entry(dlg.result)
            self._refresh_table()

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel or sel[0].startswith("week_"):
            return
        if messagebox.askyesno("Delete entry",
                               "Delete the selected entry?", parent=self):
            storage.delete_entry(sel[0])
            self._refresh_table()

    # ── Import ───────────────────────────────────────────────────

    def _import_excel(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Select timesheet Excel file(s) — hold Ctrl to pick multiple",
            filetypes=[("Excel files", "*.xlsx *.xls")],
        )
        if not paths:
            return

        total_imported = total_skipped = 0
        errors = []
        for path in paths:
            try:
                imp, skp = import_excel.import_from_file(path)
                total_imported += imp
                total_skipped += skp
            except Exception as exc:
                errors.append(f"{path}: {exc}")

        self._refresh_table()

        n = len(paths)
        msg = (f"Imported {total_imported} entr{'y' if total_imported == 1 else 'ies'}"
               f" from {n} file{'s' if n != 1 else ''}.")
        if total_skipped:
            msg += f"\n{total_skipped} duplicate{'s' if total_skipped != 1 else ''} skipped."
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors)
        messagebox.showinfo("Import complete", msg, parent=self)

    # ── Image OCR import (DLC) ───────────────────────────────────

    def _import_image(self):
        if _image_ocr_dlc is None:
            return
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Select timesheet image(s)",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return

        all_candidates: list = []
        errors: list = []
        for path in paths:
            try:
                all_candidates.extend(_image_ocr_dlc.extract_entries_from_image(path))
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")

        if errors and not all_candidates:
            messagebox.showerror("OCR failed", "\n".join(errors), parent=self)
            return
        if not all_candidates:
            messagebox.showinfo("No entries found",
                                "No timesheet entries could be detected in the image(s).",
                                parent=self)
            return

        dlg = _image_ocr_dlc.OcrPreviewDialog(self, all_candidates)
        self.wait_window(dlg)

        if dlg.confirmed_entries:
            imported, skipped = _image_ocr_dlc.save_confirmed_entries(dlg.confirmed_entries)
            self._refresh_table()
            msg = f"Imported {imported} entr{'y' if imported == 1 else 'ies'}."
            if skipped:
                msg += f"\n{skipped} duplicate{'s' if skipped != 1 else ''} skipped."
            if errors:
                msg += "\n\nErrors:\n" + "\n".join(errors)
            messagebox.showinfo("Import complete", msg, parent=self)

    # ── Excel export ─────────────────────────────────────────────

    def _export_excel(self):
        entries = storage.load_month(self._view_year, self._view_month)
        month_name = date(self._view_year, self._view_month, 1).strftime("%B %Y")
        path = filedialog.asksaveasfilename(
            parent=self,
            initialfile=f"Hours {month_name}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save timesheet as…",
        )
        if not path:
            return

        excel_export.export_month(
            entries=entries,
            year=self._view_year,
            month=self._view_month,
            save_path=path,
            fmt=storage.get_export_format(),
            include_pay=storage.get_export_include_pay(),
            pay_rate=storage.get_pay_rate(),
        )
        messagebox.showinfo("Exported", f"Timesheet saved to:\n{path}", parent=self)

