"""Tests for ui.theme — colour tokens meet WCAG AA contrast in both
appearance modes, palette lookups, and appearance start-up."""
import json
import re

import pytest
import customtkinter as ctk

from ui import theme

_HEX = re.compile(r"#[0-9a-fA-F]{6}")
_AA = 4.5

# CTk's default window / frame / nested-frame backgrounds ("blue" theme)
_BG_LIGHT = ["#ebebeb", "#dbdbdb", "#cfcfcf"]
_BG_DARK = ["#242424", "#2b2b2b", "#333333"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _luminance(hex_colour: str) -> float:
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _modes(token):
    """(light, dark) for a token that is either one colour or a pair."""
    return (token, token) if isinstance(token, str) else token


def test_contrast_helper_sanity():
    assert _contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert _contrast("#777777", "#777777") == pytest.approx(1.0)


# ── token shape ───────────────────────────────────────────────────────────────

_TOKENS = ["GREEN", "GREEN_HOVER", "RED", "RED_HOVER", "GRAY", "GRAY_HOVER",
           "PURPLE", "PURPLE_HOVER", "NAVY", "NAVY_HOVER", "BLUE", "BLUE_HOVER",
           "BLUE_TEXT_DISABLED", "ACCENT", "ACCENT_HOVER", "ON_ACCENT",
           "TEXT", "TEXT_MUTED", "TEXT_SUCCESS", "TEXT_WARNING", "TEXT_ERROR",
           "LINK", "LINK_HOVER_BG", "TODAY_RING", "CELL_HOVER"]


@pytest.mark.parametrize("name", _TOKENS)
def test_token_is_colour_or_pair(name):
    token = getattr(theme, name)
    if isinstance(token, str):
        assert _HEX.fullmatch(token)
    else:
        assert isinstance(token, tuple) and len(token) == 2
        assert all(isinstance(c, str) and _HEX.fullmatch(c) for c in token)


def test_removed_tokens_are_gone():
    assert not hasattr(theme, "ORANGE")
    assert not hasattr(theme, "is_dark")
    assert not hasattr(theme, "setup_table_style")


def test_table_palettes_have_same_keys_and_valid_hex():
    light, dark = theme.TABLE["light"], theme.TABLE["dark"]
    assert set(light) == set(dark)
    assert len(light) == 16
    for p in (light, dark):
        for key, val in p.items():
            assert _HEX.fullmatch(val), (key, val)


# ── WCAG AA contrast ──────────────────────────────────────────────────────────

_BUTTONS = ["GREEN", "GREEN_HOVER", "RED", "RED_HOVER", "GRAY", "GRAY_HOVER",
            "PURPLE", "PURPLE_HOVER", "NAVY", "NAVY_HOVER", "BLUE", "BLUE_HOVER",
            "ACCENT", "ACCENT_HOVER"]


@pytest.mark.parametrize("name", _BUTTONS)
def test_white_text_on_buttons(name):
    for colour in _modes(getattr(theme, name)):
        assert _contrast(theme.ON_ACCENT, colour) >= _AA, (name, colour)


def test_disabled_text_on_blue_button():
    assert _contrast(theme.BLUE_TEXT_DISABLED, theme.BLUE) >= _AA


@pytest.mark.parametrize("name", ["TEXT", "TEXT_MUTED", "TEXT_SUCCESS",
                                  "TEXT_WARNING", "TEXT_ERROR", "LINK"])
def test_text_on_frame_backgrounds(name):
    light, dark = getattr(theme, name)
    for bg in _BG_LIGHT:
        assert _contrast(light, bg) >= _AA, (name, light, bg)
    for bg in _BG_DARK:
        assert _contrast(dark, bg) >= _AA, (name, dark, bg)


def test_link_on_hover_background():
    # the status line's Undo keeps its link colour while hovered
    for text, hover in zip(theme.LINK, theme.LINK_HOVER_BG):
        assert _contrast(text, hover) >= _AA


def test_calendar_text_on_cell_hover():
    # hovered day cells keep regular text readable
    for text, hover in zip(theme.TEXT, theme.CELL_HOVER):
        assert _contrast(text, hover) >= _AA


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_table_contrast(mode):
    p = theme.TABLE[mode]
    pairs = [
        ("fg", "row_odd"), ("fg", "row_even"), ("fg", "week"), ("fg", "field"),
        ("sel_fg", "sel_bg"), ("head_fg", "head_bg"), ("head_fg", "head_hover"),
        ("editor_fg", "editor_bg"), ("editor_fg", "editor_bad_bg"),
    ]
    for fg, bg in pairs:
        assert _contrast(p[fg], p[bg]) >= _AA, (mode, fg, bg)


# ── palette / colour helpers ──────────────────────────────────────────────────

@pytest.mark.parametrize("mode, key", [("Dark", "dark"), ("dark", "dark"),
                                       ("LIGHT", "light"), ("Light", "light")])
def test_palette_lookup(mode, key):
    assert theme.palette(mode) is theme.TABLE[key]


def test_palette_system_follows_ctk():
    assert theme.palette("System") in (theme.TABLE["light"], theme.TABLE["dark"])


_ENTRY_KEYS = {"bg", "fg", "insertbackground", "selectbackground",
               "selectforeground", "highlightcolor", "highlightbackground"}


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_entry_colors(mode):
    p = theme.palette(mode)
    normal = theme.entry_colors(mode)
    assert set(normal) == _ENTRY_KEYS
    assert normal["bg"] == p["editor_bg"]
    assert normal["highlightcolor"] == p["editor_ring"]
    bad = theme.entry_colors(mode, invalid=True)
    assert set(bad) == _ENTRY_KEYS
    assert bad["bg"] == p["editor_bad_bg"]
    assert bad["highlightcolor"] == bad["highlightbackground"] == p["editor_bad_ring"]


@pytest.mark.parametrize("mode", ["Light", "Dark"])
def test_menu_colors(mode):
    assert set(theme.menu_colors(mode)) == {"bg", "fg", "activebackground",
                                            "activeforeground"}


# ── init_appearance ───────────────────────────────────────────────────────────

@pytest.fixture()
def fake_ctk(monkeypatch):
    calls = []
    monkeypatch.setattr(ctk, "set_appearance_mode", calls.append)
    monkeypatch.setattr(ctk, "deactivate_automatic_dpi_awareness", lambda: None)
    monkeypatch.setattr(theme, "_tune_default_theme", lambda: None)
    return calls


def test_init_appearance_uses_stored_mode(tmp_storage, fake_ctk):
    import storage
    storage.set_appearance_mode("Dark")
    theme.init_appearance()
    assert fake_ctk == ["Dark"]


def test_init_appearance_defaults_to_system(tmp_storage, fake_ctk):
    theme.init_appearance()
    assert fake_ctk == ["System"]


def test_init_appearance_survives_corrupt_data(tmp_storage, fake_ctk, monkeypatch):
    import storage
    monkeypatch.setattr(storage, "_load_raw",
                        lambda: (_ for _ in ()).throw(json.JSONDecodeError("x", "", 0)))
    theme.init_appearance()
    assert fake_ctk == ["System"]


# ── apply_table_style (needs a display) ──────────────────────────────────────

def test_apply_table_style_switches_colours():
    import tkinter as tk
    from tkinter import ttk
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    try:
        root.withdraw()
        tree = ttk.Treeview(root)
        style = ttk.Style(root)
        for mode in ("Dark", "Light", "Dark"):
            p = theme.palette(mode)
            theme.apply_table_style(tree, mode)
            assert style.theme_use() == "clam"
            assert style.lookup("Treeview", "background") == p["row_even"]
            assert style.lookup("Treeview.Heading", "background") == p["head_bg"]
            assert str(tree.tag_configure("odd", "background")) == p["row_odd"]
            assert str(tree.tag_configure("week_total", "background")) == p["week"]
    finally:
        root.destroy()
