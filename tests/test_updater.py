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
