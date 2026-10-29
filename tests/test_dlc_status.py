"""Tests for services.dlc.load_status / module / reload."""
import sys
import types

import pytest

from services import dlc


@pytest.fixture()
def fresh(monkeypatch):
    monkeypatch.setattr(dlc, "_status", None)
    monkeypatch.setattr(dlc, "_module", None)
    monkeypatch.setattr(dlc, "is_installed", lambda: True)


def _fake(**attrs):
    m = types.ModuleType("image_ocr")
    m.__dict__.update(attrs)
    return m


def test_missing(fresh, monkeypatch):
    monkeypatch.setattr(dlc, "is_installed", lambda: False)
    assert dlc.load_status() == {"state": "missing", "version": None, "error": None}
    assert dlc.module() is None


def test_ok_is_cached(fresh, monkeypatch):
    mod = _fake(__version__="2.0.0", extract_entries_from_image=lambda p: [],
                save_confirmed_entries=lambda r: (0, 0))
    monkeypatch.setitem(sys.modules, "image_ocr", mod)
    assert dlc.load_status() == {"state": "ok", "version": "2.0.0", "error": None}
    assert dlc.module() is mod
    monkeypatch.setattr(dlc, "is_installed", lambda: False)
    assert dlc.load_status()["state"] == "ok"


def test_missing_functions(fresh, monkeypatch):
    monkeypatch.setitem(sys.modules, "image_ocr", _fake(__version__="0.1"))
    st = dlc.load_status()
    assert st["state"] == "incompatible" and "extract_entries_from_image" in st["error"]
    assert dlc.module() is None


def test_import_error(fresh, monkeypatch):
    monkeypatch.setitem(sys.modules, "image_ocr", None)   # import raises ImportError
    st = dlc.load_status()
    assert st["state"] == "incompatible" and st["error"]


def test_reload_recomputes(fresh, monkeypatch):
    monkeypatch.setitem(sys.modules, "image_ocr", _fake())
    assert dlc.load_status()["state"] == "incompatible"
    monkeypatch.setattr(dlc, "is_installed", lambda: False)
    assert dlc.reload()["state"] == "missing"
    assert "image_ocr" not in sys.modules
