"""Shared UI constants and styling for all windows and dialogs.

Colours are (light, dark) tuples where the two modes need different values;
CTk widgets pick the right half themselves. Plain tk/ttk widgets can't, so
the table and inline editor get theirs from palette() and are restyled on
every appearance change. Every text/background pair here meets WCAG AA
(4.5:1) — tests/test_theme.py checks them.
"""
import customtkinter as ctk
from tkinter import ttk

# ── buttons (white text) ──────────────────────────────────────────────────────
GREEN = "#18703d"
GREEN_HOVER = "#145a32"
RED = "#c0392b"
RED_HOVER = "#922b21"
GRAY = ("#5a5a5a", "#4a4a4a")
GRAY_HOVER = ("#404040", "#5c5c5c")
PURPLE = "#6c3483"
PURPLE_HOVER = "#512e5f"
NAVY = ("#2c3e50", "#4a6583")
NAVY_HOVER = ("#1a252f", "#3b5268")
BLUE = "#1f538d"
BLUE_HOVER = "#173f6b"
BLUE_TEXT_DISABLED = "#d9d9d9"

# CTk's default blue (#3B8ED0) is too light for white text; darken it globally
ACCENT = "#1F6AA5"
ACCENT_HOVER = "#144870"
ON_ACCENT = "#FFFFFF"

# ── text on the window/frame background ──────────────────────────────────────
TEXT = ("#1a1a1a", "#DCE4EE")
TEXT_MUTED = ("#555555", "#a6a6a6")
TEXT_SUCCESS = ("#145a32", "#2ecc71")
TEXT_WARNING = ("#7a3b00", "#f0a050")
TEXT_ERROR = ("#922b21", "#f1948a")
# clickable text such as the status line's Undo, and its hover background
LINK = ("#1f538d", "#5dade2")
LINK_HOVER_BG = ("#cccccc", "#383838")

# ── calendar / time picker cells ─────────────────────────────────────────────
TODAY_RING = ("#1f538d", "#5dade2")
CELL_HOVER = ("#cccccc", "#474747")

# ── ttk table + tk inline editor (can't take tuples) ─────────────────────────
TABLE = {
    "light": {
        "row_odd": "#f0f4f8",
        "row_even": "#ffffff",
        "week": "#dce8f5",
        "fg": "#1a1a1a",
        "field": "#ffffff",
        "border": "#b3b3b3",
        "head_bg": "#36719F",
        "head_hover": "#27577D",
        "head_fg": "#ffffff",
        "sel_bg": "#1f538d",
        "sel_fg": "#ffffff",
        "editor_bg": "#ffffff",
        "editor_fg": "#1a1a1a",
        "editor_ring": "#1f538d",
        "editor_bad_bg": "#fdecea",
        "editor_bad_ring": "#c0392b",
    },
    "dark": {
        "row_odd": "#2f3136",
        "row_even": "#26282c",
        "week": "#203a55",
        "fg": "#DCE4EE",
        "field": "#26282c",
        "border": "#4a4d52",
        "head_bg": "#1f538d",
        "head_hover": "#144870",
        "head_fg": "#ffffff",
        "sel_bg": "#1F6AA5",
        "sel_fg": "#ffffff",
        "editor_bg": "#343638",
        "editor_fg": "#DCE4EE",
        "editor_ring": "#3B8ED0",
        "editor_bad_bg": "#4a2323",
        "editor_bad_ring": "#e74c3c",
    },
}

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def init_appearance():
    """Call once before the root window exists, so it never opens in the
    wrong theme."""
    ctk.deactivate_automatic_dpi_awareness()
    try:
        import storage
        mode = storage.get_appearance_mode()
    except Exception:
        mode = "System"
    ctk.set_appearance_mode(mode)
    ctk.set_default_color_theme("blue")
    _tune_default_theme()


def _tune_default_theme():
    theme = ctk.ThemeManager.theme
    swap = {"#3B8ED0": ACCENT, "#36719F": ACCENT_HOVER}
    for widget in theme.values():
        if not isinstance(widget, dict):
            continue
        for key, val in widget.items():
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                widget[key] = [swap.get(val[0].upper(), val[0]), val[1]]
    for name in ("CTkButton", "CTkSegmentedButton", "CTkOptionMenu"):
        theme[name]["text_color"] = [ON_ACCENT, ON_ACCENT]
    theme["CTkOptionMenu"]["button_hover_color"] = ["#0e3350", "#203A4F"]
    seg = theme["CTkSegmentedButton"]
    seg["fg_color"] = seg["unselected_color"] = [GRAY[0], "gray29"]
    seg["unselected_hover_color"] = [GRAY_HOVER[0], "gray41"]


def palette(mode: str) -> dict:
    """TABLE colours for 'light'/'dark' (any case). Anything else — e.g.
    'System' — means whatever CTk is currently showing."""
    key = mode.lower()
    if key not in TABLE:
        key = ctk.get_appearance_mode().lower()
    return TABLE[key]


def apply_table_style(tree: ttk.Treeview, mode: str):
    """Colour the entries Treeview (and its row tags) for *mode*. Safe to
    call repeatedly."""
    p = palette(mode)
    style = ttk.Style(tree)
    if style.theme_use() != "clam":
        style.theme_use("clam")
    style.configure("Treeview",
                    rowheight=28,
                    font=("Arial", 10),
                    background=p["row_even"],
                    foreground=p["fg"],
                    fieldbackground=p["field"],
                    bordercolor=p["border"],
                    lightcolor=p["field"],
                    darkcolor=p["field"])
    style.map("Treeview",
              background=[("selected", p["sel_bg"])],
              foreground=[("selected", p["sel_fg"])],
              bordercolor=[("focus", p["sel_bg"])],
              lightcolor=[("focus", p["sel_bg"])])
    style.configure("Treeview.Heading",
                    font=("Arial", 10, "bold"),
                    background=p["head_bg"],
                    foreground=p["head_fg"],
                    relief="flat",
                    bordercolor=p["border"],
                    lightcolor=p["head_bg"],
                    darkcolor=p["head_bg"])
    # without this the heading turns clam's light grey (#eeebe7) on hover
    style.map("Treeview.Heading",
              background=[("pressed", p["head_hover"]), ("active", p["head_hover"])],
              foreground=[("active", p["head_fg"])],
              lightcolor=[("active", p["head_hover"])],
              darkcolor=[("active", p["head_hover"])],
              relief=[("pressed", "flat"), ("active", "flat")])
    tree.tag_configure("odd", background=p["row_odd"], foreground=p["fg"])
    tree.tag_configure("even", background=p["row_even"], foreground=p["fg"])
    tree.tag_configure("week_total", background=p["week"], foreground=p["fg"])


def entry_colors(mode: str, invalid: bool = False) -> dict:
    """Config kwargs for a tk.Entry drawn over the table."""
    p = palette(mode)
    ring = p["editor_bad_ring"] if invalid else p["editor_ring"]
    return {
        "bg": p["editor_bad_bg"] if invalid else p["editor_bg"],
        "fg": p["editor_fg"],
        "insertbackground": p["editor_fg"],
        "selectbackground": p["sel_bg"],
        "selectforeground": p["sel_fg"],
        "highlightcolor": ring,
        "highlightbackground": ring,
    }


def menu_colors(mode: str) -> dict:
    """Config kwargs for a tk.Menu."""
    p = palette(mode)
    return {
        "bg": p["editor_bg"],
        "fg": p["editor_fg"],
        "activebackground": p["sel_bg"],
        "activeforeground": p["sel_fg"],
    }
