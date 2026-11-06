"""Shared pytest fixtures — redirect all file I/O to tmp_path
so tests never touch real data.json / session.json."""
import ipaddress
import os
import shutil
import socket
import tempfile

import pytest

# Safety net: set before storage/timer are first imported, so even a test
# without the fixtures (or one that calls monkeypatch.undo()) falls back to a
# throwaway dir instead of the real data next to the repo / in AppData.
_SESSION_DATA_DIR = tempfile.mkdtemp(prefix="weleho-pytest-")
os.environ["WELEHO_DATA_DIR"] = _SESSION_DATA_DIR


def pytest_unconfigure(config):
    # Only ever the throwaway dir made above, never a path from the environment.
    shutil.rmtree(_SESSION_DATA_DIR, ignore_errors=True)


def _is_loopback(host) -> bool:
    if host in (None, "", "localhost"):
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    """Tests talk to loopback servers only, so a missed mock can't reach
    GitHub. Mark a test @pytest.mark.network to lift this."""
    if request.node.get_closest_marker("network"):
        return
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect

    def getaddrinfo(host, *args, **kwargs):
        if not _is_loopback(host):
            raise OSError(f"network blocked in tests: {host!r} (mark the test 'network')")
        return real_getaddrinfo(host, *args, **kwargs)

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_loopback(address[0]):
            raise OSError(f"network blocked in tests: {address!r} (mark the test 'network')")
        return real_connect(self, address)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture(autouse=True)
def _dlc_in_tmp(tmp_path_factory, monkeypatch):
    """Point the DLC file at a temp dir, so no test can overwrite or delete
    the tracked image_ocr.py at the repo root. Tests may patch it again."""
    from services import dlc
    target = tmp_path_factory.mktemp("dlc") / dlc.DLC_FILENAME
    monkeypatch.setattr(dlc, "dlc_path", lambda: str(target))


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
    monkeypatch.setattr(storage, "last_recovery", None)
    return tmp_path


@pytest.fixture()
def tmp_timer(tmp_path, monkeypatch):
    """Redirect timer's session file to an isolated temp directory."""
    import timer as tm
    monkeypatch.setenv("WELEHO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(tm, "_DATA_DIR",     str(tmp_path))
    monkeypatch.setattr(tm, "_SESSION_FILE", str(tmp_path / "session.json"))
    return tmp_path
