"""The conftest safety nets themselves: no real network, no touching the
tracked DLC file, no personal-data copies committed by accident."""
import os
import socket
import subprocess
import urllib.request

import pytest

from services import dlc

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_outside_network_is_blocked():
    with pytest.raises(OSError, match="network blocked"):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(OSError, match="network blocked"):
        urllib.request.urlopen("https://example.com/", timeout=1)


def test_connect_to_an_outside_ip_is_blocked():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        with pytest.raises(OSError, match="network blocked"):
            s.connect(("192.0.2.1", 443))   # TEST-NET-1, never routed


def test_loopback_still_works():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        with socket.create_connection(srv.getsockname(), timeout=2):
            pass


def test_dlc_path_is_not_the_repo_file():
    path = os.path.abspath(dlc.dlc_path())
    assert not path.startswith(REPO + os.sep)
    assert os.path.basename(path) == dlc.DLC_FILENAME


@pytest.mark.parametrize("name", [
    "data.json", "data.json.bak", "data.json.tmp", "session.json", "shifts.txt",
    "data.damaged-0123456789.json", "session.bad-20260101-120000.json",
    "session.json.tmp", "backups/data-2026-01-01.json",
])
def test_personal_data_files_are_git_ignored(name):
    try:
        r = subprocess.run(["git", "check-ignore", "-q", "--no-index", name],
                           cwd=REPO, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("git not available")
    if r.returncode == 128:
        pytest.skip("not a git checkout")
    assert r.returncode == 0, f"{name} is not ignored by .gitignore"
