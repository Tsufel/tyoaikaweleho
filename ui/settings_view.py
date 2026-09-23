"""In-window settings view: about & updates, appearance, timer defaults,
shifts, export options, DLC store, keyboard shortcuts."""
import os
import threading

import customtkinter as ctk

import storage
import updater
from utils import parse_time_input, parse_pay_rate
from services import dlc
from ui import msgbox as messagebox
from ui import theme
from ui.window_utils import prepare_dialog
from version import __version__

_SHORTCUTS = [
    ("F5", "Start / stop the timer"),
    ("Ctrl+N", "Add an entry"),
    ("Enter / F2", "Edit the selected entry"),
    ("Delete", "Delete the selected entry"),
    ("Ctrl+Z", "Undo a delete (while the note is shown)"),
    ("Click a time", "Edit Time In / Time Out in place"),
    ("Ctrl+← / Ctrl+→", "Previous / next month (also PageUp / PageDown)"),
    ("Ctrl+Home", "Go to the current month"),
    ("Ctrl+E", "Export to Excel"),
    ("Ctrl+I", "Import menu"),
    ("Ctrl+,", "Open Settings"),
    ("Esc / Ctrl+S", "In Settings: back / save"),
]


def _format_rate(rate: float) -> str:
    # shortest text that reads back as the same number, so saving Settings
    # never rounds the stored rate (20.125 stays 20.125)
    text = repr(rate)
    return text[:-2] if text.endswith(".0") else text


class SettingsView(ctk.CTkFrame):
    """Settings as an embedded view. Replaces the main content while open.

    on_close(saved) is called when the user leaves the view (Back → False,
    Save → True). on_update_found(ver, url, sha_url) is called when a manual
    update check finds a newer app release. on_dlc_update_found(ver) is
    called when it finds a newer DLC version.

    The appearance choice is previewed live and reverted if the view is
    left without saving.
    """

    def __init__(self, master, dlc_module=None, dlc_update_version: str | None = None,
                 on_close=None, on_update_found=None, on_dlc_update_found=None):
        super().__init__(master, fg_color="transparent")
        self._dlc_module = dlc_module
        self._dlc_update_version = dlc_update_version
        self._on_close = on_close or (lambda saved: None)
        self._on_update_found = on_update_found or (lambda *a: None)
        self._on_dlc_update_found = on_dlc_update_found or (lambda v: None)
        # The App window outlives this view — schedule thread results there
        self._app = self.winfo_toplevel()

        # ── Header bar ─────────────────────────────────────────
        header = ctk.CTkFrame(self, height=52, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkButton(header, text="←  Back", width=90, height=34,
                      fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                      command=self.go_back).pack(side="left", padx=12, pady=9)
        ctk.CTkLabel(header, text="⚙  Settings",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(
                         side="left", padx=8)
        # In the header so it's reachable without scrolling to the bottom
        ctk.CTkButton(header, text="Save  (Ctrl+S)", width=130, height=34,
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self.save).pack(side="right", padx=12, pady=9)

        # ── Scrollable centered column ─────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        col = ctk.CTkFrame(scroll, fg_color="transparent")
        col.pack(anchor="center", pady=(4, 16))

        pad = {"padx": 24, "pady": (8, 2)}

        # ── About & Updates ────────────────────────────────────
        ctk.CTkLabel(col, text="About & Updates",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        ctk.CTkLabel(col, text=f"Työaikaweleho v{__version__}",
                     text_color=theme.TEXT_MUTED).pack(padx=24, anchor="w")
        self._check_btn = ctk.CTkButton(
            col, text="🔍  Check for updates", width=272,
            fg_color=theme.BLUE, hover_color=theme.BLUE_HOVER,
            text_color_disabled=theme.BLUE_TEXT_DISABLED,
            command=self._check_for_updates)
        self._check_btn.pack(padx=24, pady=(4, 0))

        # ── Appearance ─────────────────────────────────────────
        ctk.CTkLabel(col, text="Appearance",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._saved_appearance = storage.get_appearance_mode()
        self._appearance_var = ctk.StringVar(value=self._saved_appearance)
        ctk.CTkSegmentedButton(col, values=list(storage.APPEARANCE_MODES),
                               variable=self._appearance_var, width=272,
                               command=ctk.set_appearance_mode).pack(padx=24)
        ctk.CTkLabel(col, text="System follows the Windows light / dark setting.",
                     text_color=theme.TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(padx=24, anchor="w")

        # ── Timer ──────────────────────────────────────────────
        ctk.CTkLabel(col, text="Default start time",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._start_time_var = ctk.StringVar(value=storage.get_default_start_time())
        ctk.CTkEntry(col, textvariable=self._start_time_var, width=272).pack(padx=24)

        ctk.CTkLabel(col, text="Pay rate (€/hr)",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._pay_rate_var = ctk.StringVar(value=_format_rate(storage.get_pay_rate()))
        ctk.CTkEntry(col, textvariable=self._pay_rate_var, width=272).pack(padx=24)

        # ── Job / Shift ────────────────────────────────────────
        ctk.CTkLabel(col, text="Default job / shift",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._job_var = ctk.StringVar(value=storage.get_default_job_shift())
        self._job_combo = ctk.CTkComboBox(col, variable=self._job_var,
                              values=storage.get_job_shift_list(), width=272)
        self._job_combo.pack(padx=24)

        add_row = ctk.CTkFrame(col, fg_color="transparent")
        add_row.pack(padx=24, pady=(4, 0), fill="x")
        self._new_shift_var = ctk.StringVar()
        _shift_entry = ctk.CTkEntry(add_row, textvariable=self._new_shift_var,
                                    placeholder_text="Add new shift…", width=206)
        _shift_entry.pack(side="left")
        _shift_entry.bind("<Return>", lambda _e: self._add_shift())
        ctk.CTkButton(add_row, text="+ Add", width=62,
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self._add_shift).pack(side="left", padx=(4, 0))

        ctk.CTkButton(col, text="Edit shifts.txt  →", width=272,
                      fg_color=theme.NAVY, hover_color=theme.NAVY_HOVER,
                      command=lambda: os.startfile(storage.SHIFTS_FILE)).pack(
                          padx=24, pady=(4, 0))

        # ── Output ────────────────────────────────────────────
        ctk.CTkLabel(col, text="Output",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._fmt_var = ctk.StringVar(value=storage.get_export_format())
        ctk.CTkOptionMenu(col, variable=self._fmt_var,
                          values=["Simple", "Full"],
                          width=272).pack(padx=24)
        self._pay_chk_var = ctk.BooleanVar(value=storage.get_export_include_pay())
        ctk.CTkCheckBox(col, text="Include total pay in export",
                        variable=self._pay_chk_var).pack(
                            padx=24, pady=(6, 0), anchor="w")

        # ── DLC Store ──────────────────────────────────────────
        ctk.CTkLabel(col, text="DLC Store",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        self._dlc_section = ctk.CTkFrame(col, fg_color="transparent")
        self._dlc_section.pack(fill="x")
        self._build_dlc_section()

        # ── Keyboard shortcuts ─────────────────────────────────
        ctk.CTkLabel(col, text="Keyboard shortcuts",
                     font=ctk.CTkFont(weight="bold")).pack(**pad, anchor="w")
        keys = ctk.CTkFrame(col, fg_color="transparent")
        keys.pack(padx=24, fill="x")
        for r, (key, what) in enumerate(_SHORTCUTS):
            ctk.CTkLabel(keys, text=key, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).grid(
                             row=r, column=0, sticky="w", padx=(0, 12))
            ctk.CTkLabel(keys, text=what, anchor="w", text_color=theme.TEXT_MUTED,
                         font=ctk.CTkFont(size=12)).grid(row=r, column=1, sticky="w")

        # what the fields held on opening — Back asks before dropping edits
        self._initial = self._snapshot()

    # ── Leaving the view ─────────────────────────────────────────

    def _snapshot(self) -> tuple:
        return (self._start_time_var.get().strip(), self._pay_rate_var.get().strip(),
                self._job_var.get().strip(), self._fmt_var.get(),
                bool(self._pay_chk_var.get()), self._appearance_var.get())

    def _revert_appearance(self):
        if self._appearance_var.get() != self._saved_appearance:
            self._appearance_var.set(self._saved_appearance)
            ctk.set_appearance_mode(self._saved_appearance)

    def go_back(self):
        """Back / Escape. Asks first if a field was changed."""
        if self._snapshot() != self._initial:
            answer = messagebox.askyesnocancel(
                "Save changes?",
                "You changed some settings.\n\nSave them before going back?",
                parent=self._app)
            if answer is None:
                return
            if answer:
                self.save()
                return
        self._revert_appearance()
        self._on_close(False)

    def save(self):
        """Save / Ctrl+S. Stays open if a field is invalid."""
        if self._apply_fields():
            self._on_close(True)

    # ── DLC section (rebuilt when an update is discovered) ──────

    def _build_dlc_section(self):
        for w in self._dlc_section.winfo_children():
            w.destroy()
        # The module is only imported at startup, so check the file on disk
        # for the real state and flag when a restart is still pending
        on_disk = dlc.is_installed()
        loaded = self._dlc_module is not None
        if on_disk and not loaded:
            ctk.CTkLabel(self._dlc_section,
                         text="✅  Image OCR — installed (restart the app to activate)",
                         text_color=theme.TEXT_SUCCESS).pack(padx=24, pady=(0, 6), anchor="w")
            ctk.CTkButton(self._dlc_section, text="🗑  Remove Image OCR", width=272,
                          fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                          command=self._remove_image_ocr).pack(padx=24, pady=(0, 6))
        elif loaded and not on_disk:
            ctk.CTkLabel(self._dlc_section,
                         text="Image OCR — removed (restart the app to finish)",
                         text_color=theme.TEXT_MUTED).pack(padx=24, pady=(0, 6), anchor="w")
            ctk.CTkButton(self._dlc_section, text="⬇  Reinstall Image OCR", width=272,
                          fg_color=theme.PURPLE, hover_color=theme.PURPLE_HOVER,
                          command=self._install_image_ocr).pack(padx=24, pady=(2, 6))
        elif loaded:
            version = getattr(self._dlc_module, "__version__", "0.0.0")
            ctk.CTkLabel(self._dlc_section,
                         text=f"✅  Image OCR — installed (v{version})",
                         text_color=theme.TEXT_SUCCESS).pack(padx=24, pady=(0, 6), anchor="w")
            if self._dlc_update_version:
                ctk.CTkButton(self._dlc_section,
                              text=f"🔄  Update to v{self._dlc_update_version}", width=272,
                              fg_color=theme.PURPLE, hover_color=theme.PURPLE_HOVER,
                              command=self._install_image_ocr).pack(padx=24, pady=(0, 6))
            ctk.CTkButton(self._dlc_section, text="🗑  Remove Image OCR", width=272,
                          fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                          command=self._remove_image_ocr).pack(padx=24, pady=(0, 6))
        else:
            ctk.CTkButton(self._dlc_section, text="⬇  Install Image OCR", width=272,
                          fg_color=theme.PURPLE, hover_color=theme.PURPLE_HOVER,
                          command=self._install_image_ocr).pack(padx=24, pady=(2, 6))

    # ── Manual update check ──────────────────────────────────────

    def _check_for_updates(self):
        self._check_btn.configure(state="disabled", text="Checking…")
        dlc_installed = self._dlc_module is not None
        dlc_current = (getattr(self._dlc_module, "__version__", "0.0.0")
                       if dlc_installed else None)

        def _worker():
            outcome = {}
            try:
                outcome["release"] = updater.fetch_latest_release()
                if dlc_installed:
                    try:
                        outcome["dlc_latest"] = updater.fetch_latest_dlc_version()
                    except Exception:
                        pass  # DLC check failure shouldn't mask the app result
            except Exception as exc:
                outcome["error"] = str(exc)
            self._app.after(0, lambda: self._on_check_done(outcome, dlc_current))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_check_done(self, outcome: dict, dlc_current: str | None):
        if self.winfo_exists():
            self._check_btn.configure(state="normal", text="🔍  Check for updates")

        if "error" in outcome:
            messagebox.showerror(
                "Check failed",
                f"Could not check for updates:\n{outcome['error']}",
                parent=self._app)
            return

        dlc_latest = outcome.get("dlc_latest")
        dlc_newer = (dlc_latest and dlc_current
                     and updater._is_newer(dlc_latest, dlc_current))
        if dlc_newer:
            self._dlc_update_version = dlc_latest
            self._on_dlc_update_found(dlc_latest)
            if self.winfo_exists():
                self._build_dlc_section()

        release = outcome.get("release")
        if release and updater._is_newer(release[0], __version__):
            self._on_update_found(*release)
        else:
            msg = f"You're up to date (v{__version__})."
            if dlc_newer:
                msg += (f"\n\nA newer Image OCR DLC (v{dlc_latest}) is available —"
                        " see the DLC Store below.")
            messagebox.showinfo("Up to date", msg, parent=self._app)

    # ── Shifts ───────────────────────────────────────────────────

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
                                f"'{js}' is already in the shift list.",
                                parent=self._app)

    # ── DLC install/remove ───────────────────────────────────────

    def _install_image_ocr(self):
        prog = ctk.CTkToplevel(self)
        prog.title("Installing DLC")
        prog.geometry("360x110")
        prog.resizable(False, False)
        prog.protocol("WM_DELETE_WINDOW", lambda: None)  # can't cancel mid-download
        ctk.CTkLabel(prog, text="Downloading image_ocr.py…").pack(pady=(24, 6))
        bar = ctk.CTkProgressBar(prog, mode="indeterminate")
        bar.pack(padx=30, fill="x")
        bar.start()
        prepare_dialog(prog, self._app)

        # Download off the UI thread so the window keeps repainting
        def _worker():
            try:
                outcome = ("ok", dlc.install())
            except Exception as exc:
                outcome = ("error", str(exc))
            try:
                self._app.after(0, lambda: self._on_install_done(prog, bar, outcome))
            except RuntimeError:
                pass  # app closed mid-download

        threading.Thread(target=_worker, daemon=True).start()

    def _on_install_done(self, prog, bar, outcome):
        bar.stop()
        prog.destroy()
        kind, value = outcome
        if kind == "error":
            messagebox.showerror("Install failed", value, parent=self._app)
            return
        verified = value
        msg = (
            "Image OCR DLC installed! ✅\n\n"
            "Restart the app to activate the 📷 Import from Image button.\n\n"
            "Uses Windows built-in OCR — no extra software needed.\n"
            "For best results with Finnish timesheets, ensure Finnish\n"
            "is added in Windows Settings → Language."
        )
        if not verified:
            msg += ("\n\n⚠ Note: the publisher hasn't published a checksum "
                    "for this DLC version, so the download could not be "
                    "integrity-verified.")
        messagebox.showinfo("DLC installed", msg, parent=self._app)
        self._close_keeping_edits()

    def _remove_image_ocr(self):
        if not messagebox.askyesno(
            "Remove Image OCR",
            "Remove the Image OCR DLC?\n\n"
            "The 📷 Import from Image button will disappear after restart.\n"
            "Your saved entries are not affected.",
            parent=self._app,
        ):
            return
        try:
            dlc.remove()
        except dlc.DlcError as exc:
            messagebox.showerror("Remove failed", str(exc), parent=self._app)
            return
        messagebox.showinfo(
            "DLC removed",
            "Image OCR DLC removed.\n\nRestart the app for the change to take effect.",
            parent=self._app)
        self._close_keeping_edits()

    def _close_keeping_edits(self):
        """Leave the view after a DLC change without dropping field edits.
        If a field is invalid, stay open so the user can fix it."""
        if self._apply_fields():
            self._on_close(True)
        elif self.winfo_exists():
            self._build_dlc_section()

    # ── Save ─────────────────────────────────────────────────────

    def _apply_fields(self) -> bool:
        """Validate and store the form fields. Returns False (after showing
        an error) if a field is invalid or the settings could not be written."""
        t = parse_time_input(self._start_time_var.get())
        if t is None:
            messagebox.showerror("Invalid time",
                                 "Default start time must be a valid time (e.g. 09:30).",
                                 parent=self._app)
            return False
        rate = parse_pay_rate(self._pay_rate_var.get())
        if rate is None:
            messagebox.showerror("Invalid rate",
                                 "Pay rate must be a positive number (e.g. 20 or 20,50).",
                                 parent=self._app)
            return False
        appearance = self._appearance_var.get()
        try:
            storage.set_default_start_time(t)
            storage.set_pay_rate(rate)
            storage.set_default_job_shift(self._job_var.get().strip())
            storage.set_export_format(self._fmt_var.get())
            storage.set_export_include_pay(self._pay_chk_var.get())
            if appearance in storage.APPEARANCE_MODES:
                storage.set_appearance_mode(appearance)
        except OSError as exc:
            messagebox.showerror("Could not save settings",
                                 f"Settings could not be written:\n\n{exc}",
                                 parent=self._app)
            return False
        self._saved_appearance = appearance
        self._initial = self._snapshot()
        return True
