"""Shared UI constants and styling for all windows and dialogs."""
import customtkinter as ctk
from tkinter import ttk

GREEN = "#27ae60"
GREEN_HOVER = "#1e8449"
RED = "#c0392b"
RED_HOVER = "#922b21"
GRAY = "#7f8c8d"
GRAY_HOVER = "#636e72"
PURPLE = "#6c3483"
PURPLE_HOVER = "#512e5f"
NAVY = "#2c3e50"
NAVY_HOVER = "#1a252f"
BLUE = "#1f538d"
ORANGE = "#e67e22"

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def init_appearance():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")


def is_dark() -> bool:
    return ctk.get_appearance_mode().lower() == "dark"


def setup_table_style():
    """Configure the ttk.Treeview style used by the entries table."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview",
                    rowheight=28,
                    font=("Arial", 10),
                    background="#2b2b2b" if is_dark() else "#ffffff",
                    foreground="white" if is_dark() else "black",
                    fieldbackground="#2b2b2b" if is_dark() else "#ffffff")
    style.configure("Treeview.Heading",
                    font=("Arial", 10, "bold"),
                    background=BLUE if is_dark() else "#3b8ed0",
                    foreground="white")
    style.map("Treeview",
              background=[("selected", BLUE)],
              foreground=[("selected", "white")])
