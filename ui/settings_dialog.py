"""Settings dialog: timer defaults, shifts, export options, DLC store."""
import os

import customtkinter as ctk
from tkinter import messagebox

import storage
from utils import parse_time_input
from services import dlc
from ui import theme


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, dlc_module=None, dlc_update_version: str | None = None):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("320x560")
        self.resizable(False, False)
        self.grab_set()
        self.changed = False
        self._dlc_module = dlc_module
        self._dlc_update_version = dlc_update_version

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
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self._add_shift).pack(side="left", padx=(4, 0))

        ctk.CTkButton(self, text="Edit shifts.txt  →", width=272,
                      fg_color=theme.NAVY, hover_color=theme.NAVY_HOVER,
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
        if self._dlc_module is not None:
            version = getattr(self._dlc_module, "__version__", "0.0.0")
            ctk.CTkLabel(self, text=f"✅  Image OCR — installed (v{version})",
                         text_color=theme.GREEN).pack(padx=24, pady=(0, 6), anchor="w")
            if self._dlc_update_version:
                ctk.CTkButton(self,
                              text=f"🔄  Update to v{self._dlc_update_version}", width=272,
                              fg_color=theme.PURPLE, hover_color=theme.PURPLE_HOVER,
                              command=self._install_image_ocr).pack(padx=24, pady=(0, 6))
            ctk.CTkButton(self, text="🗑  Remove Image OCR", width=272,
                          fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
                          command=self._remove_image_ocr).pack(padx=24, pady=(0, 6))
        else:
            ctk.CTkButton(self, text="⬇  Install Image OCR", width=272,
                          fg_color=theme.PURPLE, hover_color=theme.PURPLE_HOVER,
                          command=self._install_image_ocr).pack(padx=24, pady=(2, 6))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=(8, 16))
        ctk.CTkButton(row, text="Save", width=120,
                      fg_color=theme.GREEN, hover_color=theme.GREEN_HOVER,
                      command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Cancel", width=120,
                      fg_color=theme.GRAY, hover_color=theme.GRAY_HOVER,
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
        prog = ctk.CTkToplevel(self)
        prog.title("Installing DLC")
        prog.geometry("360x110")
        prog.resizable(False, False)
        prog.grab_set()
        ctk.CTkLabel(prog, text="Downloading image_ocr.py…").pack(pady=(24, 6))
        bar = ctk.CTkProgressBar(prog, mode="indeterminate")
        bar.pack(padx=30, fill="x")
        bar.start()
        prog.update()

        try:
            verified = dlc.install()
        except dlc.DlcError as exc:
            bar.stop()
            prog.destroy()
            messagebox.showerror("Install failed", str(exc), parent=self)
            return
        except Exception as exc:
            bar.stop()
            prog.destroy()
            messagebox.showerror("Install failed", str(exc), parent=self)
            return

        bar.stop()
        prog.destroy()
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
        messagebox.showinfo("DLC installed", msg, parent=self)
        self.changed = True
        self.destroy()

    def _remove_image_ocr(self):
        if not messagebox.askyesno(
            "Remove Image OCR",
            "Remove the Image OCR DLC?\n\n"
            "The 📷 Import from Image button will disappear after restart.\n"
            "Your saved entries are not affected.",
            parent=self,
        ):
            return
        try:
            dlc.remove()
        except dlc.DlcError as exc:
            messagebox.showerror("Remove failed", str(exc), parent=self)
            return
        messagebox.showinfo(
            "DLC removed",
            "Image OCR DLC removed.\n\nRestart the app for the change to take effect.",
            parent=self)
        self.changed = True
        self.destroy()

    def _save(self):
        t = parse_time_input(self._start_time_var.get())
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
