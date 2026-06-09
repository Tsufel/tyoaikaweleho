"""Shared pure-logic utilities.

Kept separate from app.py so the test suite can import them without
pulling in customtkinter (which needs a display).
"""
import os
import sys


def parse_time_input(t: str) -> str | None:
    """Normalise loose time strings to 'HH:MM'. Returns None if unrecognisable.

    Accepted (24 h): '9:30', '09:30', '9.30', '09.30', '930', '1345'
    """
    t = t.strip().replace(".", ":")
    if t.isdigit():
        if len(t) == 3:       # "930"  → "9:30"
            t = t[0] + ":" + t[1:]
        elif len(t) == 4:     # "1345" → "13:45"
            t = t[:2] + ":" + t[2:]
        else:
            return None
    parts = t.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return None


def is_valid_time(t: str) -> bool:
    return parse_time_input(t) is not None


def get_app_dir() -> str:
    """Directory where app assets (splash.png, toolbar.png, icon.ico) live.
    Works both when running from source and when frozen by PyInstaller."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
