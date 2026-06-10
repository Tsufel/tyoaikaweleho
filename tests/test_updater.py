"""Tests for updater — version comparison, URL validation, checksum helpers."""
import hashlib
import sys

import pytest

import updater
from version import GITHUB_REPO


# ── version comparison ────────────────────────────────────────────────────────

def test_is_newer_basic():
    assert updater._is_newer("1.1.0", "1.0.0") is True
    assert updater._is_newer("1.0.0", "1.1.0") is False
    assert updater._is_newer("1.0.0", "1.0.0") is False


def test_is_newer_multi_digit():
    assert updater._is_newer("1.10.0", "1.9.0") is True


def test_is_newer_malformed():
    assert updater._is_newer("abc", "1.0.0") is False
    assert updater._is_newer("1.0.0", "") is False


# ── download URL validation ───────────────────────────────────────────────────

def test_safe_url_accepts_own_release_asset():
    url = f"https://github.com/{GITHUB_REPO}/releases/download/v1.1.0/Setup.exe"
    assert updater._is_safe_download_url(url) is True


def test_safe_url_rejects_http():
    url = f"http://github.com/{GITHUB_REPO}/releases/download/v1.1.0/Setup.exe"
    assert updater._is_safe_download_url(url) is False


def test_safe_url_rejects_other_host():
    assert updater._is_safe_download_url(
        "https://evil.example.com/Setup.exe") is False


def test_safe_url_rejects_other_repo():
    assert updater._is_safe_download_url(
        "https://github.com/attacker/repo/releases/download/v9/Setup.exe") is False


def test_safe_url_rejects_lookalike_host():
    assert updater._is_safe_download_url(
        f"https://github.com.evil.example/{GITHUB_REPO}/releases/download/v1/Setup.exe"
    ) is False


# ── release parsing ───────────────────────────────────────────────────────────

def _release(tag="v1.2.0", assets=()):
    return {"tag_name": tag, "assets": list(assets)}


def _asset(name):
    return {"name": name,
            "browser_download_url": f"https://github.com/{GITHUB_REPO}/releases/download/v1.2.0/{name}"}


def test_parse_release_with_exe_and_sha():
    data = _release(assets=[_asset("Setup.exe"), _asset("Setup.exe.sha256")])
    ver, exe_url, sha_url = updater._parse_release(data)
    assert ver == "1.2.0"
    assert exe_url.endswith("/Setup.exe")
    assert sha_url.endswith("/Setup.exe.sha256")


def test_parse_release_exe_only():
    data = _release(assets=[_asset("Setup.exe")])
    ver, exe_url, sha_url = updater._parse_release(data)
    assert ver == "1.2.0"
    assert exe_url.endswith("/Setup.exe")
    assert sha_url is None


def test_parse_release_no_exe_asset():
    data = _release(assets=[_asset("notes.txt")])
    assert updater._parse_release(data) is None


def test_parse_release_no_assets():
    assert updater._parse_release(_release()) is None


def test_parse_release_malformed_raises():
    with pytest.raises(KeyError):
        updater._parse_release({"assets": []})  # missing tag_name


def test_fetch_latest_release_returns_none_when_no_releases(monkeypatch):
    """GitHub answers 404 when a repo has never published a release."""
    import urllib.error

    def _raise_404(*a, **kw):
        raise urllib.error.HTTPError("url", 404, "Not Found", {}, None)

    monkeypatch.setattr(updater.urllib.request, "urlopen", _raise_404)
    assert updater.fetch_latest_release() is None


def test_fetch_latest_release_reraises_other_http_errors(monkeypatch):
    import urllib.error

    def _raise_500(*a, **kw):
        raise urllib.error.HTTPError("url", 500, "Server Error", {}, None)

    monkeypatch.setattr(updater.urllib.request, "urlopen", _raise_500)
    with pytest.raises(urllib.error.HTTPError):
        updater.fetch_latest_release()


# ── checksum helpers ──────────────────────────────────────────────────────────

def test_file_sha256(tmp_path):
    p = tmp_path / "blob.bin"
    p.write_bytes(b"hello world")
    assert updater._file_sha256(str(p)) == hashlib.sha256(b"hello world").hexdigest()


# ── apply_update guards ───────────────────────────────────────────────────────

def test_apply_update_noop_from_source(monkeypatch):
    """Running from source must never download or launch anything."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    updater.apply_update("https://evil.example.com/Setup.exe")  # no exception


def test_apply_update_rejects_untrusted_url(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    with pytest.raises(updater.UpdateError):
        updater.apply_update("https://evil.example.com/Setup.exe")
