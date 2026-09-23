"""Small popup time picker: scrollable list of times in 30-minute increments."""
import customtkinter as ctk

from utils import parse_time_input
from ui import theme
from ui.window_utils import clamp_to_workarea, prepare_dialog

SLOTS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
_SIZE = (130, 320)


def nearest_slot(t: str | None) -> int | None:
    """Index in SLOTS of the half-hour closest to *t* (ties round up), or
    None if *t* isn't a time. 23:50 rounds to 00:00."""
    t = parse_time_input(t) if t else None
    if t is None:
        return None
    h, m = map(int, t.split(":"))
    return (h * 60 + m + 15) // 30 % len(SLOTS)


class TimePickerPopup(ctk.CTkToplevel):
    """Scrollable list of "HH:MM" times (30-min increments), opened scrolled
    to the slot nearest *initial*. After wait_window(), .result holds the
    picked time, or None when dismissed."""

    def __init__(self, parent, initial: str | None = None, anchor_widget=None):
        super().__init__(parent)
        self.title("Pick a start time")
        self.geometry(f"{_SIZE[0]}x{_SIZE[1]}")
        self.resizable(False, False)
        self.result: str | None = None
        self._index = nearest_slot(initial)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=6, pady=6)

        for i, t in enumerate(SLOTS):
            if i == self._index:
                style = {"fg_color": theme.GREEN, "hover_color": theme.GREEN_HOVER,
                         "text_color": "white"}
            else:
                style = {"fg_color": "transparent", "hover_color": theme.CELL_HOVER,
                         "text_color": theme.TEXT}
            ctk.CTkButton(self._scroll, text=t, height=28,
                          command=lambda t=t: self._pick(t), **style,
                          ).pack(fill="x", pady=1)

        self.bind("<Escape>", lambda _e: self.destroy())
        if self._index is not None:
            for seq in ("<Return>", "<KP_Enter>"):
                self.bind(seq, lambda _e: self._pick(SLOTS[self._index]))
            # the list only has a height once the window is on screen
            self.bind("<Map>", self._on_map)
            self.after(100, self._scroll_to_selected)

        # Position below the anchor widget, kept on its monitor
        if anchor_widget is not None:
            scale = self._get_window_scaling()
            w, h = round(_SIZE[0] * scale), round(_SIZE[1] * scale)
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
            x, y = clamp_to_workarea(self, x, y, w, h)
            self.geometry(f"+{x}+{y}")
        prepare_dialog(self, parent, center=anchor_widget is None)

    def _on_map(self, event):
        if event.widget is self:
            self.after_idle(self._scroll_to_selected)

    def _scroll_to_selected(self):
        if self._index is None or not self.winfo_exists():
            return
        canvas = self._scroll._parent_canvas
        canvas.update_idletasks()
        first, last = canvas.yview()
        target = (self._index + 0.5) / len(SLOTS) - (last - first) / 2
        canvas.yview_moveto(max(0.0, target))

    def _pick(self, t: str):
        self.result = t
        self.destroy()
