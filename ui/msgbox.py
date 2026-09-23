"""Themed stand-ins for tkinter.messagebox.

Same function names, arguments and return values, so modules can simply
``from ui import msgbox as messagebox``. Unlike the native boxes these
follow the app's light/dark mode. Enter picks the highlighted button,
Escape cancels, arrow keys / Tab move between buttons.
"""
import tkinter as tk

import customtkinter as ctk

from ui import theme
from ui.window_utils import prepare_dialog

_ICONS = {
    "info": ("ℹ", theme.LINK),
    "question": ("?", theme.LINK),
    "warning": ("⚠", theme.TEXT_WARNING),
    "error": ("✖", theme.TEXT_ERROR),
}
_STYLES = {
    "primary": {},
    "secondary": {"fg_color": theme.GRAY, "hover_color": theme.GRAY_HOVER},
    "danger": {"fg_color": theme.RED, "hover_color": theme.RED_HOVER},
}
_FOCUS_RING = ("#1a1a1a", "#ffffff")


class _MessageBox(ctk.CTkToplevel):
    """buttons: [(key, label, style)] left to right; style is a _STYLES key.
    .result is the key of the button pressed, or *cancel* when closed."""

    def __init__(self, parent, title, message, buttons, default, cancel, icon):
        super().__init__(parent)
        self.title(title or "")
        self.resizable(False, False)
        self.result = cancel
        self._cancel = cancel

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(18, 12))
        glyph, color = _ICONS.get(icon, _ICONS["info"])
        ctk.CTkLabel(body, text=glyph, text_color=color, width=36,
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left", anchor="n")
        ctk.CTkLabel(body, text=message or "", justify="left", anchor="w",
                     wraplength=380).pack(side="left", fill="both", expand=True, padx=(10, 0))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 16))
        widgets = {}
        for key, label, style in reversed(buttons):
            btn = ctk.CTkButton(row, text=label, width=max(90, 9 * len(label)),
                                height=32, border_width=2,
                                border_color=_STYLES[style].get("fg_color", theme.ACCENT),
                                command=lambda k=key: self._choose(k),
                                **_STYLES[style])
            btn.pack(side="right", padx=(8, 0))
            widgets[key] = btn
        self._buttons: list[tuple[str, ctk.CTkButton]] = [
            (key, widgets[key]) for key, _label, _style in buttons]
        keys = [k for k, _ in self._buttons]
        self._current = keys.index(default) if default in keys else 0
        self._show_focus()

        self.protocol("WM_DELETE_WINDOW", lambda: self._choose(self._cancel))
        self.bind("<Return>", lambda _e: self._invoke_current())
        self.bind("<KP_Enter>", lambda _e: self._invoke_current())
        self.bind("<space>", lambda _e: self._invoke_current())
        self.bind("<Escape>", lambda _e: self._choose(self._cancel))
        for seq, step in (("<Left>", -1), ("<Right>", 1), ("<Tab>", 1),
                          ("<Shift-Tab>", -1), ("<ISO_Left_Tab>", -1)):
            self.bind(seq, lambda _e, s=step: self._move(s))

        if icon in ("warning", "error"):
            self.bell()
        prepare_dialog(self, parent)

    def _move(self, step: int):
        self._current = (self._current + step) % len(self._buttons)
        self._show_focus()
        return "break"

    def _show_focus(self):
        for i, (_key, btn) in enumerate(self._buttons):
            if i == self._current:
                btn.configure(border_color=_FOCUS_RING)
            else:
                btn.configure(border_color=btn.cget("fg_color"))

    def _invoke_current(self):
        self._choose(self._buttons[self._current][0])
        return "break"

    def _choose(self, key):
        self.result = key
        self.destroy()


def _parent(options: dict) -> tk.Misc:
    parent = options.get("parent")
    if parent is None:
        parent = tk._get_default_root("show a message box")
    return parent


def _run(title, message, buttons, default, cancel, icon, options):
    parent = _parent(options)
    box = _MessageBox(parent, title, message, buttons,
                      options.get("default", default), cancel,
                      options.get("icon", icon))
    parent.wait_window(box)
    return box.result


_OK = [("ok", "OK", "primary")]


def showinfo(title=None, message=None, **options) -> str:
    return _run(title, message, _OK, "ok", "ok", "info", options)


def showwarning(title=None, message=None, **options) -> str:
    return _run(title, message, _OK, "ok", "ok", "warning", options)


def showerror(title=None, message=None, **options) -> str:
    return _run(title, message, _OK, "ok", "ok", "error", options)


def askyesno(title=None, message=None, **options) -> bool:
    return _run(title, message,
                [("yes", "Yes", "primary"), ("no", "No", "secondary")],
                "yes", "no", "question", options) == "yes"


def askyesnocancel(title=None, message=None, **options) -> bool | None:
    answer = _run(title, message,
                  [("yes", "Yes", "primary"), ("no", "No", "secondary"),
                   ("cancel", "Cancel", "secondary")],
                  "yes", "cancel", "question", options)
    return {"yes": True, "no": False}.get(answer)


def askchoice(title, message, buttons, default=None, cancel=None, **options):
    """Custom-button prompt. *buttons* is [(key, label)] or
    [(key, label, style)] left to right, style 'primary'/'secondary'/'danger'
    (default: first button primary, the rest secondary). Returns the chosen
    key, or *cancel* if the box was closed / Escape pressed."""
    full = []
    for i, b in enumerate(buttons):
        style = b[2] if len(b) > 2 else ("primary" if i == 0 else "secondary")
        full.append((b[0], b[1], style))
    return _run(title, message, full, default if default is not None else full[0][0],
                cancel, "question", options)
