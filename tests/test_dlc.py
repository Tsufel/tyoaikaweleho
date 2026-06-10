"""Tests for services.dlc — URL validation, hash verification, atomic install."""
import hashlib

import pytest

from services import dlc


_REPO = "Tsufel/tyoaikaweleho"
_PAYLOAD = b"# fake dlc module\n__version__ = '9.9.9'\n"


# ── URL validation ────────────────────────────────────────────────────────────

def test_safe_url_accepts_dlc_branch_raw():
    assert dlc._is_safe_url(
        f"https://raw.githubusercontent.com/{_REPO}/dlc/image_ocr.py", _REPO) is True


def test_safe_url_rejects_http():
    assert dlc._is_safe_url(
        f"http://raw.githubusercontent.com/{_REPO}/dlc/image_ocr.py", _REPO) is False


def test_safe_url_rejects_other_host():
    assert dlc._is_safe_url(
        f"https://evil.example.com/{_REPO}/dlc/image_ocr.py", _REPO) is False


def test_safe_url_rejects_other_repo():
    assert dlc._is_safe_url(
        "https://raw.githubusercontent.com/attacker/repo/dlc/image_ocr.py",
        _REPO) is False


# ── install with hash verification ───────────────────────────────────────────

@pytest.fixture()
def fake_remote(monkeypatch, tmp_path):
    """Patch network + destination so install() runs fully offline."""
    state = {"version_txt": b"", "payload": _PAYLOAD}

    def _fetch(url, repo):
        if url.endswith("dlc_version.txt"):
            return state["version_txt"]
        return state["payload"]

    monkeypatch.setattr(dlc, "_fetch", _fetch)
    monkeypatch.setattr(dlc, "_check_repo_configured", lambda: _REPO)
    monkeypatch.setattr(dlc, "dlc_path",
                        lambda: str(tmp_path / "image_ocr.py"))
    state["dest"] = tmp_path / "image_ocr.py"
    return state


def test_install_verified(fake_remote):
    digest = hashlib.sha256(_PAYLOAD).hexdigest()
    fake_remote["version_txt"] = f"9.9.9 {digest}".encode()
    assert dlc.install() is True
    assert fake_remote["dest"].read_bytes() == _PAYLOAD


def test_install_unverified_old_format(fake_remote):
    fake_remote["version_txt"] = b"9.9.9"
    assert dlc.install() is False
    assert fake_remote["dest"].exists()


def test_install_rejects_checksum_mismatch(fake_remote):
    fake_remote["version_txt"] = b"9.9.9 " + (b"0" * 64)
    with pytest.raises(dlc.DlcError):
        dlc.install()
    assert not fake_remote["dest"].exists()


def test_install_rejects_malformed_hash(fake_remote):
    fake_remote["version_txt"] = b"9.9.9 nothex"
    with pytest.raises(dlc.DlcError):
        dlc.install()


def test_mismatch_leaves_existing_dlc_untouched(fake_remote):
    fake_remote["dest"].write_bytes(b"# existing good dlc")
    fake_remote["version_txt"] = b"9.9.9 " + (b"0" * 64)
    with pytest.raises(dlc.DlcError):
        dlc.install()
    assert fake_remote["dest"].read_bytes() == b"# existing good dlc"


# ── remove ────────────────────────────────────────────────────────────────────

def test_remove_missing_file_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(dlc, "dlc_path", lambda: str(tmp_path / "nope.py"))
    with pytest.raises(dlc.DlcError):
        dlc.remove()


def test_remove_deletes_file(monkeypatch, tmp_path):
    p = tmp_path / "image_ocr.py"
    p.write_bytes(_PAYLOAD)
    monkeypatch.setattr(dlc, "dlc_path", lambda: str(p))
    dlc.remove()
    assert not p.exists()
