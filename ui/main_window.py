"""Main application window: composition, navigation, import/export, updates."""
import os
import sys
import threading
import traceback

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
from datetime import date, datetime, timedelta

import storage
import timer as timer_module
import excel_export
import import_excel
import updater
from services import dlc as dlc_service
from utils import get_app_dir, format_duration
from ui import msgbox as messagebox
from ui import theme
from ui.dialogs import (MonthPickerDialog, EditEntryDialog, ChangelogDialog,
                        RecoverShiftDialog)
from ui.settings_view import SettingsView
from ui.timer_panel import TimerPanel
from ui.entries_table import EntriesTable
from ui.window_utils import (prepare_dialog, fit_geometry, geometry_on_screen,
                             parse_geometry)
from version import __version__

theme.init_appearance()

_image_ocr_dlc = dlc_service.load_module()
_DLC_VERSION = getattr(_image_ocr_dlc, "__version__", "0.0.0") if _image_ocr_dlc else None

_DEFAULT_SIZE = (860, 700)
_FLASH_MS = 8000
# widgets where Ctrl+arrows / Home / PageUp already mean something
_TEXT_CLASSES = {"Entry", "TEntry", "Text", "TCombobox", "Spinbox"}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Työaikaweleho")
        self.minsize(700, 560)
        self.withdraw()  # hidden until splash finishes

        self._dlc_update_version = None
        self._update_dialog_open = False
        self._showing_error = False
        self._flash_job = None
        self._undo_action = None
        today = date.today()
        self._view_year = today.year
        self._view_month = today.month

        self._restore_geometry()
        self._build_ui()
        self._refresh()
        self._bind_shortcuts()
        self.bind("<Configure>", self._track_geometry, add="+")
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

    # ── Errors ───────────────────────────────────────────────────

    def report_callback_exception(self, exc, val, tb):
        """Unhandled errors in Tk callbacks. The exe has no console, so
        without this they would vanish — log them and tell the user."""
        text = "".join(traceback.format_exception(exc, val, tb))
        storage.append_error_log(text)
        if sys.stderr is not None:
            sys.stderr.write(text)
        # TclErrors are mostly callbacks firing on already-destroyed
        # widgets — log only. One box at a time, however often it repeats.
        if issubclass(exc, tk.TclError) or self._showing_error:
            return
        self._showing_error = True
        try:
            messagebox.showerror(
                "Something went wrong",
                f"{exc.__name__}: {val}\n\nYour saved shifts are not affected. "
                f"The details were written to:\n{storage.ERROR_LOG}",
                parent=self)
        except Exception:
            pass
        finally:
            self._showing_error = False

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
            if self._start_zoomed:
                self.state("zoomed")
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

    # ── Window geometry ──────────────────────────────────────────

    def _restore_geometry(self):
        """Last session's size and position if it is still on a connected
        monitor, else the default size fitted to the screen. Raw Tk
        geometry (physical pixels) both ways, so DPI scaling can't drift."""
        try:
            saved = storage.get_window_geometry()
        except (OSError, ValueError):
            saved = None
        self._start_zoomed = False
        if saved and geometry_on_screen(self, saved[0]):
            # still shrunk to fit, in case the screen got smaller since
            geom = fit_geometry(self, *parse_geometry(saved[0]))
            self._start_zoomed = saved[1]
        else:
            scale = self._get_window_scaling()
            w, h = (round(v * scale) for v in _DEFAULT_SIZE)
            geom = fit_geometry(self, w, h)
        self.wm_geometry(geom)
        # not read back: a withdrawn window reports 1x1 until it's mapped
        self._normal_geometry = geom
        self._zoomed = self._start_zoomed

    def _track_geometry(self, event):
        # bound on the root, so this also sees every child widget's resize
        if event.widget is not self:
            return
        state = self.state()
        if state == "normal":
            self._normal_geometry = self.wm_geometry()
        if state in ("normal", "zoomed"):
            self._zoomed = state == "zoomed"

    def _save_geometry(self):
        try:
            if self.state() == "normal":
                self._normal_geometry = self.wm_geometry()
            storage.set_window_geometry(self._normal_geometry, self._zoomed)
        except (OSError, ValueError, tk.TclError):
            pass  # never block closing over this

    def _quit(self):
        self._save_geometry()
        self.destroy()

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
                      command=lambda: self._shift_month(-1)).pack(side="left")

        self._month_label = ctk.CTkLabel(
            nav, text="", width=180, cursor="hand2",
            font=ctk.CTkFont(size=15, weight="bold"))
        self._month_label.pack(side="left", padx=6)
        self._month_label.bind("<Button-1>", lambda _e: self._open_month_picker())

        ctk.CTkButton(nav, text="►", width=34, height=34,
                      command=lambda: self._shift_month(1)).pack(side="left")

        self._import_btn = ctk.CTkButton(
            top, text="Import  ▾", width=110,
            fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
            command=self._post_import_menu)
        self._import_btn.pack(side="right", padx=12, pady=8)
        self._import_menu = tk.Menu(self, tearoff=0)
        self._import_menu.add_command(label="From Excel…", command=self._import_excel)
        if _image_ocr_dlc is not None:
            self._import_menu.add_command(label="From image (OCR)…",
                                          command=self._import_image)
        ctk.CTkButton(top, text="⚙  Settings", width=110,
                      fg_color=theme.NAVY, hover_color=theme.NAVY_HOVER,
                      command=self._open_settings).pack(side="right", padx=(0, 6), pady=8)

        # ── Timer card ───────────────────────────────────────────
        self._timer_panel = TimerPanel(self._main_view, on_entry_saved=self._show_entry,
                                       on_status=self.flash)
        self._timer_panel.pack(fill="x", padx=16, pady=(10, 0))

        # ── Entries section ──────────────────────────────────────
        entries_header = ctk.CTkFrame(self._main_view, fg_color="transparent")
        entries_header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(entries_header, text="Shifts this month",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(entries_header, text="+ Add entry  (Ctrl+N)",
                      width=170, height=30,
                      command=self._add_manual).pack(side="right")

        # Status line: short notes such as "Deleted … Undo"
        flash_row = ctk.CTkFrame(entries_header, fg_color="transparent")
        flash_row.pack(side="left", fill="x", expand=True, padx=(14, 8))
        self._flash_label = ctk.CTkLabel(flash_row, text="", anchor="w",
                                         text_color=theme.TEXT_MUTED)
        self._flash_label.pack(side="left")
        self._flash_btn = ctk.CTkButton(
            flash_row, text="", width=60, height=24,
            fg_color="transparent", hover_color=theme.LINK_HOVER_BG,
            text_color=theme.LINK, border_width=1, border_color=theme.LINK,
            command=self._undo)

        # ── Table ────────────────────────────────────────────────
        self._table = EntriesTable(self._main_view, on_change=self._refresh,
                                   on_activate=self._edit_selected,
                                   on_delete=self._delete_selected,
                                   on_select=self._update_action_buttons,
                                   on_status=self.flash)
        self._table.pack(fill="both", expand=True, padx=16)

        # ── Bottom bar ───────────────────────────────────────────
        bottom = ctk.CTkFrame(self._main_view, height=52, corner_radius=0)
        bottom.pack(fill="x", pady=(4, 0))
        bottom.pack_propagate(False)

        self._edit_btn = ctk.CTkButton(
            bottom, text="✏  Edit", width=100, height=34,
            fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
            command=self._edit_selected)
        self._edit_btn.pack(side="left", padx=(12, 4), pady=9)
        self._delete_btn = ctk.CTkButton(
            bottom, text="🗑  Delete", width=100, height=34,
            fg_color=theme.RED, hover_color=theme.RED_HOVER,
            command=self._delete_selected)
        self._delete_btn.pack(side="left", padx=4, pady=9)

        self._total_label = ctk.CTkLabel(
            bottom, text="Total: 0:00",
            font=ctk.CTkFont(size=13, weight="bold"))
        self._total_label.pack(side="left", padx=20)

        ctk.CTkButton(bottom, text="Export to Excel  (Ctrl+E)", width=190, height=34,
                      fg_color=theme.BLUE, hover_color=theme.BLUE_HOVER,
                      command=self._export_excel).pack(side="right", padx=12, pady=9)

        self._update_month_label()

    # ── Refresh ──────────────────────────────────────────────────

    def _refresh(self, select: str | None = None):
        total_minutes = self._table.refresh(self._view_year, self._view_month,
                                            select=select)
        th, tm = divmod(total_minutes, 60)
        earnings = total_minutes / 60 * storage.get_pay_rate()
        self._total_label.configure(
            text=f"Total: {th}:{tm:02d}  (€{earnings:.2f})")
        self._update_month_label()
        self._update_action_buttons()

    def _show_entry(self, entry: storage.WorkEntry):
        """Switch to the entry's month and select it — after it was added,
        edited or restored, possibly into another month."""
        try:
            d = date.fromisoformat(entry.date)
            self._view_year, self._view_month = d.year, d.month
        except ValueError:
            pass
        self._refresh(select=entry.id)

    def _update_action_buttons(self):
        state = "normal" if self._table.selected_entry_id() else "disabled"
        self._edit_btn.configure(state=state)
        self._delete_btn.configure(state=state)

    # ── Status line ──────────────────────────────────────────────

    def flash(self, msg: str, action_text: str | None = None, action=None):
        """Show *msg* above the table for a few seconds, optionally with a
        button (e.g. Undo, also on Ctrl+Z) that runs *action*."""
        if self._flash_job is not None:
            self.after_cancel(self._flash_job)
        self._flash_label.configure(text=msg)
        self._undo_action = action
        if action is not None:
            self._flash_btn.configure(text=action_text or "Undo")
            self._flash_btn.pack(side="left", padx=(8, 0))
        else:
            self._flash_btn.pack_forget()
        self._flash_job = self.after(_FLASH_MS, self._clear_flash)

    def _clear_flash(self):
        if self._flash_job is not None:
            self.after_cancel(self._flash_job)
        self._flash_job = None
        self._undo_action = None
        self._flash_label.configure(text="")
        self._flash_btn.pack_forget()

    def _undo(self):
        action = self._undo_action
        if action is not None:
            self._clear_flash()
            action()

    # ── Keyboard shortcuts ───────────────────────────────────────

    def _bind_shortcuts(self):
        # (sequences, action, also while typing in a text field)
        shortcuts = [
            (("<Control-n>", "<Control-N>"), self._add_manual, True),
            (("<Control-e>", "<Control-E>"), self._export_excel, True),
            (("<Control-i>", "<Control-I>"), self._post_import_menu, True),
            (("<Control-comma>",), self._open_settings, True),
            (("<Control-Left>", "<Prior>"), lambda: self._shift_month(-1), False),
            (("<Control-Right>", "<Next>"), lambda: self._shift_month(1), False),
            (("<Control-Home>",), self._go_to_current_month, False),
            (("<F5>",), self._timer_panel.toggle, True),
        ]
        for seqs, action, in_fields in shortcuts:
            handler = self._shortcut(action, in_fields)
            for seq in seqs:
                self.bind(seq, handler)
        # only while its Undo is on screen, so Ctrl+Z never acts blind
        for seq in ("<Control-z>", "<Control-Z>"):
            self.bind(seq, self._on_ctrl_z)
        # Settings view keys
        self.bind("<Escape>", self._on_escape)
        for seq in ("<Control-s>", "<Control-S>"):
            self.bind(seq, self._on_ctrl_s)

    def _idle(self) -> bool:
        """No dialog open and the main view showing. The timer card is
        hidden while Settings is open — F5 mustn't start or stop a shift
        the user can't see."""
        return self._settings_view is None and self.grab_current() is None

    def _typing(self) -> bool:
        try:
            widget = self.focus_get()
        except (KeyError, tk.TclError):  # e.g. a combobox dropdown has focus
            return False
        return widget is not None and widget.winfo_class() in _TEXT_CLASSES

    def _shortcut(self, action, in_fields: bool):
        def handler(_event=None):
            if not self._idle() or (not in_fields and self._typing()):
                return None
            action()
            return "break"
        return handler

    def _on_ctrl_z(self, _event=None):
        if self._undo_action is None or not self._idle():
            return None
        self._undo()
        return "break"

    def _on_escape(self, _event=None):
        if self._settings_view is not None and self.grab_current() is None:
            self._settings_view.go_back()
            return "break"
        return None

    def _on_ctrl_s(self, _event=None):
        if self._settings_view is not None and self.grab_current() is None:
            self._settings_view.save()
            return "break"
        return None

    # ── Post-splash sequence ──────────────────────────────────────

    def _on_after_splash(self):
        """Runs once after the splash screen closes: changelog check, then crash recovery."""
        # a failing changelog step must not skip recovery, or the next START
        # would overwrite the unfinished shift
        for step in (self._check_for_new_version, self._check_for_crash_recovery):
            try:
                step()
            except Exception:
                self.report_callback_exception(*sys.exc_info())
        self._table.focus_table()

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
        over_limit = datetime.now() - start_dt >= timedelta(hours=8)
        suggested_end = (start_dt + timedelta(hours=8) if over_limit
                         else datetime.now()).strftime("%H:%M")

        # asked again until the shift is saved, resumed or discarded, so a
        # failed save can't leave it for START to overwrite
        while True:
            dlg = RecoverShiftDialog(self, start_dt, job_shift, suggested_end, over_limit)
            self.wait_window(dlg)
            answer = dlg.result

            if answer == "discard":
                timer_module.clear_saved_session()
                return

            if answer == "resume":
                self._view_year, self._view_month = start_dt.year, start_dt.month
                self._timer_panel.start(start_time=start_dt, job_shift=job_shift)
                self._refresh()
                return
            # ("save", "HH:MM")
            entry = storage.WorkEntry(
                id=storage.new_entry_id(),
                date=start_dt.strftime("%Y-%m-%d"),
                job_shift=job_shift,
                time_in=start_dt.strftime("%H:%M"),
                time_out=answer[1],
            )
            try:
                storage.save_entry(entry)
            except OSError as exc:
                messagebox.showerror("Could not save shift",
                                     f"The shift could not be saved:\n\n{exc}\n\n"
                                     "Close any program that may be locking data.json "
                                     "and try again, or resume the shift for now.",
                                     parent=self)
                suggested_end = answer[1]
                continue
            timer_module.clear_saved_session()
            self._show_entry(entry)
            return

    # ── Close handler ────────────────────────────────────────────

    def _on_close(self):
        grab = self.grab_current()
        if grab is not None and grab is not self and grab.winfo_exists():
            # a dialog is waiting for an answer — closing now would lose it.
            # Closing from the taskbar while minimised hides the dialog along
            # with the window, so bring both back.
            try:
                if self.state() == "iconic":
                    self.deiconify()
                dialog = grab.winfo_toplevel()
                if dialog.state() == "withdrawn":
                    dialog.deiconify()
                dialog.lift()
                grab.focus_force()
            except tk.TclError:
                pass
            return
        if not self._table.commit_edit():
            return  # an inline edit couldn't be saved; it's still open
        if not self._timer_panel.is_running:
            self._quit()
            return
        timer = self._timer_panel
        minutes = int(timer.elapsed_seconds() // 60)
        answer = messagebox.askyesnocancel(
            "Shift still running",
            f"A shift is running (started {timer.start_time_str()}, "
            f"{format_duration(minutes)} ago).\n\n"
            "Yes  →  Stop the shift, save it, then close\n"
            "No   →  Close anyway (shift will be recovered on next open)\n"
            "Cancel  →  Stay open",
            parent=self,
        )
        if answer is True:
            if timer.stop(confirm=False):
                self._quit()
        elif answer is False:
            self._quit()
        # answer is None (Cancel) → do nothing

    # ── Auto-update ──────────────────────────────────────────────

    def _on_update_available(self, new_ver: str, url: str, sha256_url: str | None):
        # Called from a background thread — marshal to UI thread
        self.after(0, lambda: self._show_update_dialog(new_ver, url, sha256_url))

    def _on_dlc_update_available(self, new_version: str):
        # Called from a background thread — marshal to UI thread
        self.after(0, lambda: setattr(self, "_dlc_update_version", new_version))

    def _show_update_dialog(self, new_ver: str, url: str, sha256_url: str | None):
        # The startup check and Settings → "Check for updates" can both land here
        if self._update_dialog_open:
            return
        self._update_dialog_open = True
        try:
            if not messagebox.askyesno(
                "Update available",
                f"Version {new_ver} is available (you have {__version__}).\n\n"
                "Download and install now?\n\n"
                "(The app will close and relaunch automatically.)",
                parent=self,
            ):
                return
        finally:
            self._update_dialog_open = False
        if not getattr(sys, "frozen", False):
            messagebox.showinfo("Update", "Updates can only be installed from the "
                                "installed app, not when running from source.",
                                parent=self)
            return
        self._run_update(url, sha256_url)

    def _run_update(self, url: str, sha256_url: str | None):
        """Download and launch the installer off the UI thread so the
        window stays responsive while it downloads."""
        self._save_geometry()   # the installer closes the app without _on_close
        prog_win = ctk.CTkToplevel(self)
        prog_win.title("Updating")
        prog_win.geometry("320x100")
        prog_win.resizable(False, False)
        prog_win.protocol("WM_DELETE_WINDOW", lambda: None)  # can't cancel mid-download
        ctk.CTkLabel(prog_win, text="Downloading update…").pack(pady=(18, 8))
        bar = ctk.CTkProgressBar(prog_win, mode="indeterminate", width=260)
        bar.pack()
        bar.start()
        prepare_dialog(prog_win, self)

        def _done(error: str | None):
            bar.stop()
            prog_win.destroy()
            if error:
                messagebox.showerror("Update failed", error, parent=self)

        def _worker():
            try:
                updater.apply_update(url, sha256_url)
                error = None
            except updater.UpdateError as exc:
                error = str(exc)
            except Exception as exc:
                error = f"Unexpected error: {exc}"
            try:
                self.after(0, lambda: _done(error))
            except RuntimeError:
                pass  # app already closing for the installer

        threading.Thread(target=_worker, daemon=True).start()

    # ── Settings ─────────────────────────────────────────────────

    def _open_settings(self):
        if self._settings_view is not None:
            return
        if not self._table.commit_edit():
            return  # the inline edit couldn't be saved; it's still open
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
        self._table.focus_table()

    # ── Month navigation ─────────────────────────────────────────

    def _shift_month(self, delta: int):
        if not self._table.commit_edit():
            return  # leaving the month would drop the unsaved inline edit
        index = self._view_year * 12 + (self._view_month - 1) + delta
        self._view_year, self._view_month = divmod(index, 12)
        self._view_month += 1
        self._refresh()

    def _go_to_current_month(self):
        today = date.today()
        if (self._view_year, self._view_month) != (today.year, today.month):
            if not self._table.commit_edit():
                return
            self._view_year, self._view_month = today.year, today.month
            self._refresh()

    def _update_month_label(self):
        name = date(self._view_year, self._view_month, 1).strftime("%B %Y")
        self._month_label.configure(text=f"{name} ▾")

    def _open_month_picker(self):
        if not self._table.commit_edit():
            return
        dlg = MonthPickerDialog(self, self._view_year, self._view_month)
        self.wait_window(dlg)
        if dlg.result:
            self._view_year, self._view_month = dlg.result
            self._refresh()

    # ── Entry actions ────────────────────────────────────────────

    def _find_entry(self, entry_id: str) -> storage.WorkEntry | None:
        return next((e for e in storage.load_all_entries() if e.id == entry_id), None)

    def _add_manual(self):
        if not self._table.commit_edit():
            return
        today = date.today()
        if (today.year, today.month) == (self._view_year, self._view_month):
            default = today
        else:
            default = date(self._view_year, self._view_month, 1)
        # the dialog stays open, with what was typed, until the save succeeds
        dlg = EditEntryDialog(self, default_date=default, on_save=storage.save_entry)
        self.wait_window(dlg)
        if dlg.result:
            self._show_entry(dlg.result)

    def _edit_selected(self):
        entry_id = self._table.selected_entry_id()
        if not entry_id:
            return
        if not self._table.commit_edit():
            return
        entry = self._find_entry(entry_id)
        if not entry:
            return
        dlg = EditEntryDialog(self, entry=entry, on_save=storage.update_entry)
        self.wait_window(dlg)
        if dlg.result:
            self._show_entry(dlg.result)

    def _delete_selected(self):
        entry_id = self._table.selected_entry_id()
        if not entry_id:
            return
        if not self._table.commit_edit():
            return
        entry = self._find_entry(entry_id)
        if not entry:
            return
        desc = _describe(entry)
        if not messagebox.askyesno("Delete entry", f"Delete the shift {desc}?",
                                   icon="warning", parent=self):
            return
        try:
            storage.delete_entry(entry_id)
        except OSError as exc:
            messagebox.showerror("Could not delete entry",
                                 f"The entry could not be deleted:\n\n{exc}\n\n"
                                 "Close any program that may be locking data.json "
                                 "and try again.", parent=self)
            return
        self._refresh()
        self.flash(f"Deleted {desc}.", "Undo", lambda: self._restore_entry(entry))

    def _restore_entry(self, entry: storage.WorkEntry):
        try:
            storage.save_entry(entry)
        except OSError as exc:
            messagebox.showerror("Could not restore entry",
                                 f"The entry could not be restored:\n\n{exc}",
                                 parent=self)
            # keep the deleted entry reachable instead of losing it
            self.flash(f"Could not restore {_describe(entry)}.", "Retry",
                       lambda: self._restore_entry(entry))
            return
        self._show_entry(entry)
        self.flash(f"Restored {_describe(entry)}.")

    # ── Import ───────────────────────────────────────────────────

    def _post_import_menu(self):
        # tk.Menu doesn't take CTk's (light, dark) colours — recolour per post
        self._import_menu.configure(**theme.menu_colors(self._get_appearance_mode()))
        btn = self._import_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        try:
            self._import_menu.tk_popup(x, y)
        finally:
            self._import_menu.grab_release()

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
            try:
                imported, skipped = _image_ocr_dlc.save_confirmed_entries(
                    dlg.confirmed_entries)
            except OSError as exc:
                messagebox.showerror("Import failed",
                                     f"The entries could not be saved:\n\n{exc}",
                                     parent=self)
                return
            self._refresh()
            msg = f"Imported {imported} entr{'y' if imported == 1 else 'ies'}."
            if skipped:
                msg += f"\n{skipped} duplicate{'s' if skipped != 1 else ''} skipped."
            if errors:
                msg += "\n\nErrors:\n" + "\n".join(errors)
            messagebox.showinfo("Import complete", msg, parent=self)

    # ── Excel export ─────────────────────────────────────────────

    def _export_excel(self):
        if not self._table.commit_edit():
            return
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

        try:
            excel_export.export_month(
                entries=entries,
                year=self._view_year,
                month=self._view_month,
                save_path=path,
                fmt=storage.get_export_format(),
                include_pay=storage.get_export_include_pay(),
                pay_rate=storage.get_pay_rate(),
            )
        except PermissionError:
            messagebox.showerror(
                "Export failed",
                f"Could not write:\n{path}\n\n"
                "The file is probably open in Excel — close it and try again.",
                parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export:\n\n{exc}",
                                 parent=self)
            return
        messagebox.showinfo("Exported", f"Timesheet saved to:\n{path}", parent=self)


def _describe(entry: storage.WorkEntry) -> str:
    """'on Tue 23 Sep, 09:00–17:00'"""
    try:
        day = date.fromisoformat(entry.date).strftime("%a %d %b")
    except ValueError:
        day = entry.date
    return f"on {day}, {entry.time_in}–{entry.time_out}"
