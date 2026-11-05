"""updater download path against a loopback http.server: truncated
downloads are rejected (even without a .sha256 asset) and never launched,
and failed downloads leave no temp file behind."""
import hashlib
import http.server
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request

import pytest

import updater
from version import GITHUB_REPO

PAYLOAD = b"MZ" + bytes(range(256)) * 400
DL = f"/{GITHUB_REPO}/releases/download/v9.9.9/"


class _Exited(Exception):
    pass


@pytest.fixture()
def server(tmp_path, monkeypatch):
    routes = {}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            code, body, claim = routes.get(self.path, (404, b"", None))
            self.send_response(code)
            self.send_header("Content-Length", str(claim if claim is not None else len(body)))
            self.end_headers()
            self.wfile.write(body)
            if claim is not None:
                self.close_connection = True

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    real = urllib.request.urlopen

    def urlopen(req, timeout=None, context=None):
        url = req.full_url
        if url.startswith("https://github.com"):
            url = base + url[len("https://github.com"):]
        return real(url, timeout=timeout)

    launched = []

    def fake_exit(code):
        raise _Exited(code)

    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **k: launched.append(args))
    monkeypatch.setattr(updater.os, "_exit", fake_exit)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    tmpdir = tmp_path / "dl"
    tmpdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmpdir))
    yield routes, launched, tmpdir
    srv.shutdown()
    srv.server_close()


URL = f"https://github.com{DL}Setup.exe"
SHA_URL = URL + ".sha256"


def test_download_to_rejects_truncated_body(server, tmp_path):
    routes, _, _ = server
    routes[DL + "Setup.exe"] = (200, PAYLOAD[:1000], len(PAYLOAD))
    with pytest.raises(updater.UpdateError, match="incomplete"):
        updater._download_to(URL, str(tmp_path / "x.exe"))


def test_download_to_full_body(server, tmp_path):
    routes, _, _ = server
    routes[DL + "Setup.exe"] = (200, PAYLOAD, None)
    updater._download_to(URL, str(tmp_path / "x.exe"))
    assert (tmp_path / "x.exe").read_bytes() == PAYLOAD


def test_apply_update_truncated_without_sha_never_launches(server):
    routes, launched, tmpdir = server
    routes[DL + "Setup.exe"] = (200, PAYLOAD[:1000], len(PAYLOAD))
    with pytest.raises(updater.UpdateError):
        updater.apply_update(URL, None)
    assert launched == [] and os.listdir(tmpdir) == []


def test_apply_update_without_sha_never_launches_full_download(server):
    """A release with no .sha256 asset can't be verified: refused outright."""
    routes, launched, tmpdir = server
    routes[DL + "Setup.exe"] = (200, PAYLOAD, None)
    with pytest.raises(updater.UpdateError, match="checksum"):
        updater.apply_update(URL, None)
    assert launched == [] and os.listdir(tmpdir) == []


def test_apply_update_untrusted_sha_url_refused(server):
    routes, launched, tmpdir = server
    routes[DL + "Setup.exe"] = (200, PAYLOAD, None)
    with pytest.raises(updater.UpdateError, match="not trusted"):
        updater.apply_update(URL, "https://example.com/Setup.exe.sha256")
    assert launched == [] and os.listdir(tmpdir) == []


def test_downloaded_installer_named_for_cleanup(server):
    routes, launched, tmpdir = server
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    routes[DL + "Setup.exe"] = (200, PAYLOAD, None)
    routes[DL + "Setup.exe.sha256"] = (200, sha.encode(), None)
    with pytest.raises(_Exited):
        updater.apply_update(URL, SHA_URL)
    [args] = launched
    assert os.path.basename(args[0]).startswith("weleho-update-")
    updater.cleanup_old_exe()
    assert os.listdir(tmpdir) == []


def test_cleanup_leaves_other_temp_files(server):
    _, _, tmpdir = server
    (tmpdir / "weleho-update-abc.exe").write_bytes(b"x")
    (tmpdir / "someone-else.exe").write_bytes(b"x")
    (tmpdir / "weleho-update-notes.txt").write_bytes(b"x")
    updater.cleanup_old_exe()
    assert sorted(os.listdir(tmpdir)) == ["someone-else.exe", "weleho-update-notes.txt"]


def test_apply_update_wrong_hash_leaves_nothing(server):
    routes, launched, tmpdir = server
    routes[DL + "Setup.exe"] = (200, PAYLOAD, None)
    routes[DL + "Setup.exe.sha256"] = (200, b"0" * 64, None)
    with pytest.raises(updater.UpdateError, match="mismatch"):
        updater.apply_update(URL, SHA_URL)
    assert launched == [] and os.listdir(tmpdir) == []


def test_apply_update_http_error_leaves_nothing(server):
    routes, launched, tmpdir = server
    routes[DL + "Setup.exe"] = (500, b"boom", None)
    with pytest.raises(urllib.error.HTTPError):
        updater.apply_update(URL, SHA_URL)
    assert launched == [] and os.listdir(tmpdir) == []


def test_apply_update_good_hash_launches_verified_file(server):
    routes, launched, tmpdir = server
    sha = hashlib.sha256(PAYLOAD).hexdigest()
    routes[DL + "Setup.exe"] = (200, PAYLOAD, None)
    routes[DL + "Setup.exe.sha256"] = (200, f"{sha}  Setup.exe\n".encode(), None)
    with pytest.raises(_Exited):
        updater.apply_update(URL, SHA_URL)
    [args] = launched
    assert args[1:] == ["/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]
    with open(args[0], "rb") as f:
        assert f.read() == PAYLOAD
