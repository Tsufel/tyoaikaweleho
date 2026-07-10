"""Small popup time picker: scrollable list of times in 30-minute increments."""
import customtkinter as ctk

from ui import theme


class TimePickerPopup(ctk.CTkToplevel):
    """Scrollable list of "HH:MM" times (30-min increments). After
    wait_window(), .result holds the picked time, or None when dismissed."""

    def __init__(self, parent, initial: str | None = None, anchor_widget=None):
        super().__init__(parent)
        self.title("Pick a start time")
        self.geometry("130x320")
        self.resizable(False, False)
        self.grab_set()
        self.result: str | None = None

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=6, pady=6)

        times = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
        for t in times:
            selected = t == initial
            ctk.CTkButton(
                scroll, text=t, height=28,
                fg_color=theme.GREEN if selected else "transparent",
                hover_color=theme.GREEN_HOVER,
                text_color="white" if selected else ("black", "white"),
                command=lambda t=t: self._pick(t),
            ).pack(fill="x", pady=1)

        self.bind("<Escape>", lambda _e: self.destroy())

        # Position next to the anchor widget (clamped to the screen)
        self.update_idletasks()
        if anchor_widget is not None:
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            x = max(0, min(x, self.winfo_screenwidth() - w))
            y = max(0, min(y, self.winfo_screenheight() - h))
            self.geometry(f"+{x}+{y}")

    def _pick(self, t: str):
        self.result = t
        self.destroy()
