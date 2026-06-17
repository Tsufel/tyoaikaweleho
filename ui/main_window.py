"""Main application window: composition, navigation, import/export, updates."""
import os

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import date, datetime, timedelta

import storage
import timer as timer_module
import excel_export
import import_excel
import updater
from services import dlc as dlc_service
from utils import get_app_dir
from ui import theme
from ui.dialogs import MonthPickerDialog, EditEntryDialog, ChangelogDialog
from ui.settings_view import SettingsView
from ui.timer_panel import TimerPanel
from ui.entries_table import EntriesTable
from version import __version__

theme.init_appearance()

_image_ocr_dlc = dlc_service.load_module()
_DLC_VERSION = getattr(_image_ocr_dlc, "__version__", "0.0.0") if _image_ocr_dlc else None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Työaikaweleho")
        self.geometry("860x700")
        self.minsize(700, 560)
        self.withdraw()  # hidden until splash finishes

        self._dlc_update_version = None
        today = date.today()
        self._view_year = today.year
        self._view_month = today.month

        theme.setup_table_style()
        self._build_ui()
        self._refresh()
        self.bind("<F5>", lambda _e: self._timer_panel.toggle())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_icon()
        # Splash reveals the main window and triggers crash recovery when done
        self.after(50, self._show_splash)
        # Background update check (silently ignored if network unavailable)
        try:
            updater.check_for_update(__version__, self._on_update_available)
            if _image_ocr_dlc is not None:
                updater.check_for_dlc_update(_DLC_VERSION, self._on_dlc_update_available)
        except Exception:
            pass

    # ── Icon & splash ─────────────────────────────────────────────

    def _setup_icon(self):
        """Set window/taskbar icon from icon.ico (preferred) or toolbar.png."""
        app_dir = get_app_dir()
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
        png_path = os.path.join(get_app_dir(), "splash.png")

        def _finish():
            self.deiconify()
            self.lift()
            self.after(100, self._on_after_splash)

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

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self):
        # All main content lives in one frame so the settings view can
        # swap in/out without touching individual widgets
        self._main_view = ctk.CTkFrame(self, fg_color="transparent")
        self._main_view.pack(fill="both", expand=True)
        self._settings_view: SettingsView | None = None

        # ── Top bar ──────────────────────────────────────────────
        top = ctk.CTkFrame(self._main_view, height=52, corner_radius=0)
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
                      fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                      command=self._import_excel).pack(side="right", padx=12, pady=8)
        if _image_ocr_dlc is not None:
            ctk.CTkButton(top, text="📷  Import from Image…", width=190,
                          fg_color=theme.PURPLE, hover_color=theme.PURPLE_HOVER,
                          command=self._import_image).pack(side="right", padx=(0, 6), pady=8)
        ctk.CTkButton(top, text="⚙  Settings", width=110,
                      fg_color=theme.NAVY, hover_color=theme.NAVY_HOVER,
                      command=self._open_settings).pack(side="right", padx=(0, 6), pady=8)

        # ── Timer card ───────────────────────────────────────────
        self._timer_panel = TimerPanel(self._main_view, on_entry_saved=self._refresh)
        self._timer_panel.pack(fill="x", padx=16, pady=(10, 0))

        # ── Entries section ──────────────────────────────────────
        entries_header = ctk.CTkFrame(self._main_view, fg_color="transparent")
        entries_header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(entries_header, text="Shifts this month",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(entries_header, text="+ Add entry manually",
                      width=160, height=30,
                      command=self._add_manual).pack(side="right")

        # ── Table ────────────────────────────────────────────────
        self._table = EntriesTable(self._main_view, on_change=self._refresh,
                                   on_activate=self._edit_selected)
        self._table.pack(fill="both", expand=True, padx=16)

        # ── Bottom bar ───────────────────────────────────────────
        bottom = ctk.CTkFrame(self._main_view, height=52, corner_radius=0)
        bottom.pack(fill="x", pady=(4, 0))
        bottom.pack_propagate(False)

        ctk.CTkButton(bottom, text="✏  Edit", width=100, height=34,
                      fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                      command=self._edit_selected).pack(side="left", padx=(12, 4), pady=9)
        ctk.CTkButton(bottom, text="🗑  Delete", width=100, height=34,
                      fg_color=theme.RED, hover_color=theme.RED_HOVER,
                      command=self._delete_selected).pack(side="left", padx=4, pady=9)

        self._total_label = ctk.CTkLabel(
            bottom, text="Total: 0:00",
            font=ctk.CTkFont(size=13, weight="bold"))
        self._total_label.pack(side="left", padx=20)

        ctk.CTkButton(bottom, text="Export to Excel  →", width=160, height=34,
                      fg_color=theme.BLUE,
                      command=self._export_excel).pack(side="right", padx=12, pady=9)

        self._update_month_label()

    # ── Refresh ──────────────────────────────────────────────────

    def _refresh(self):
        total_minutes = self._table.refresh(self._view_year, self._view_month)
        th, tm = divmod(total_minutes, 60)
        earnings = total_minutes / 60 * storage.get_pay_rate()
        self._total_label.configure(
            text=f"Total: {th}:{tm:02d}  (€{earnings:.2f})")
        self._update_month_label()

    # ── Post-splash sequence ──────────────────────────────────────

    def _on_after_splash(self):
        """Runs once after the splash screen closes: changelog check, then crash recovery."""
        self._check_for_new_version()
        self._check_for_crash_recovery()

    def _check_for_new_version(self):
        """Show a 'What's new' dialog if the app was just updated."""
        import changelog as _cl
        last = storage.get_last_seen_version()
        storage.set_last_seen_version(__version__)
        if last is None or last == __version__:
            return
        def _ver(v):
            try:
                return tuple(int(x) for x in v.split("."))
            except ValueError:
                return (0, 0, 0)
        newer = {v: items for v, items in _cl.CHANGELOG.items() if _ver(v) > _ver(last)}
        if not newer:
            return
        dlg = ChangelogDialog(self, newer)
        self.wait_window(dlg)

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
            self._refresh()
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
            self._timer_panel.start(start_time=start_dt, job_shift=job_shift)
            self._view_year  = start_dt.year
            self._view_month = start_dt.month
            self._refresh()

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
            self._refresh()

        else:                   # Discard
            timer_module.clear_saved_session()

    # ── Close handler ────────────────────────────────────────────

    def _on_close(self):
        if not self._timer_panel.is_running:
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
            self._timer_panel.stop()
            self.destroy()
        elif answer is False:
            self.destroy()
        # answer is None (Cancel) → do nothing

    # ── Auto-update ──────────────────────────────────────────────

    def _on_update_available(self, new_ver: str, url: str, sha256_url: str | None):
        # Called from a background thread — marshal to UI thread
        self.after(0, lambda: self._show_update_dialog(new_ver, url, sha256_url))

    def _on_dlc_update_available(self, new_version: str):
        # Called from a background thread — marshal to UI thread
        self.after(0, lambda: setattr(self, "_dlc_update_version", new_version))

    def _show_update_dialog(self, new_ver: str, url: str, sha256_url: str | None):
        if messagebox.askyesno(
            "Update available",
            f"Version {new_ver} is available (you have {__version__}).\n\n"
            "Download and install now?\n\n"
            "(The app will close and relaunch automatically.)",
            parent=self,
        ):
            try:
                updater.apply_update(url, sha256_url)
            except updater.UpdateError as exc:
                messagebox.showerror("Update failed", str(exc), parent=self)

    # ── Settings ─────────────────────────────────────────────────

    def _open_settings(self):
        if self._settings_view is not None:
            return
        self._main_view.pack_forget()
        self._settings_view = SettingsView(
            self,
            dlc_module=_image_ocr_dlc,
            dlc_update_version=self._dlc_update_version,
            on_close=self._close_settings,
            on_update_found=self._show_update_dialog,
            on_dlc_update_found=lambda v: setattr(self, "_dlc_update_version", v),
        )
        self._settings_view.pack(fill="both", expand=True)

    def _close_settings(self, saved: bool):
        if self._settings_view is None:
            return
        self._settings_view.destroy()
        self._settings_view = None
        self._main_view.pack(fill="both", expand=True)
        if saved:
            self._timer_panel.refresh_settings()
            self._refresh()

    # ── Month navigation ─────────────────────────────────────────

    def _prev_month(self):
        if self._view_month == 1:
            self._view_month, self._view_year = 12, self._view_year - 1
        else:
            self._view_month -= 1
        self._refresh()

    def _next_month(self):
        if self._view_month == 12:
            self._view_month, self._view_year = 1, self._view_year + 1
        else:
            self._view_month += 1
        self._refresh()

    def _update_month_label(self):
        name = date(self._view_year, self._view_month, 1).strftime("%B %Y")
        self._month_label.configure(text=f"{name} ▾")

    def _open_month_picker(self):
        dlg = MonthPickerDialog(self, self._view_year, self._view_month)
        self.wait_window(dlg)
        if dlg.result:
            self._view_year, self._view_month = dlg.result
            self._refresh()

    # ── Entry actions ────────────────────────────────────────────

    def _add_manual(self):
        dlg = EditEntryDialog(
            self, default_date=date(self._view_year, self._view_month, 1))
        self.wait_window(dlg)
        if dlg.result:
            storage.save_entry(dlg.result)
            self._refresh()

    def _edit_selected(self):
        entry_id = self._table.selected_entry_id()
        if not entry_id:
            return
        all_entries = storage.load_all_entries()
        entry = next((e for e in all_entries if e.id == entry_id), None)
        if not entry:
            return
        dlg = EditEntryDialog(self, entry=entry)
        self.wait_window(dlg)
        if dlg.result:
            storage.update_entry(dlg.result)
            self._refresh()

    def _delete_selected(self):
        entry_id = self._table.selected_entry_id()
        if not entry_id:
            return
        if messagebox.askyesno("Delete entry",
                               "Delete the selected entry?", parent=self):
            storage.delete_entry(entry_id)
            self._refresh()

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

        self._refresh()

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
            self._refresh()
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
