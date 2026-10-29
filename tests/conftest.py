"""Shared pytest fixtures — redirect all file I/O to tmp_path
so tests never touch real data.json / session.json."""
import os
import tempfile

import pytest

# Safety net: set before storage/timer are first imported, so even a test
# without the fixtures (or one that calls monkeypatch.undo()) falls back to a
# throwaway dir instead of the real data next to the repo / in AppData.
os.environ["WELEHO_DATA_DIR"] = tempfile.mkdtemp(prefix="weleho-pytest-")


@pytest.fixture()
def tmp_storage(tmp_path, monkeypatch):
    """Redirect the storage module's file paths to an isolated temp directory."""
    import storage
    monkeypatch.setenv("WELEHO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(storage, "DATA_DIR",      str(tmp_path))
    monkeypatch.setattr(storage, "DATA_FILE",     str(tmp_path / "data.json"))
    monkeypatch.setattr(storage, "SHIFTS_FILE",   str(tmp_path / "shifts.txt"))
    monkeypatch.setattr(storage, "_APPDATA_FILE", str(tmp_path / "appdata.json"))
    monkeypatch.setattr(storage, "ERROR_LOG",     str(tmp_path / "error.log"))
    return tmp_path


@pytest.fixture()
def tmp_timer(tmp_path, monkeypatch):
    """Redirect timer's session file to an isolated temp directory."""
    import timer as tm
    monkeypatch.setenv("WELEHO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tm, "_DATA_DIR",     str(tmp_path))
    monkeypatch.setattr(tm, "_SESSION_FILE", str(tmp_path / "session.json"))
    return tmp_path
