"""Secure install/remove of the optional Image OCR DLC.

The DLC is a single Python file (image_ocr.py) published on the repo's
``dlc`` branch alongside ``dlc_version.txt``. Because the DLC is executable
code, the download is verified against a SHA-256 hash published in
``dlc_version.txt`` (format: ``<version> <sha256>`` on the first line; the
old version-only format is tolerated but reported as unverified) and only
moved into place atomically once it is complete and valid.
"""
import hashlib
import os
import sys
import tempfile
import urllib.parse
import urllib.request

_DOWNLOAD_TIMEOUT = 30  # seconds

DLC_FILENAME = "image_ocr.py"


class DlcError(Exception):
    """Raised when a DLC download fails or fails validation."""


def load_module():
    """Import and return the optional image_ocr DLC module, or None when
    it isn't installed (or its dependencies are missing)."""
    try:
        import image_ocr
        return image_ocr
    except ImportError:
        return None


def dlc_path() -> str:
    """Where the DLC file must live: next to the exe when frozen,
    next to the source tree otherwise."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), DLC_FILENAME)
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DLC_FILENAME)


def is_installed() -> bool:
    return os.path.exists(dlc_path())


def _check_repo_configured() -> str:
    try:
        from version import GITHUB_REPO
    except ImportError:
        GITHUB_REPO = ""
    if not GITHUB_REPO or "YOUR_GITHUB_USERNAME" in GITHUB_REPO:
        raise DlcError(
            "The GitHub repository hasn't been set up yet.\n"
            "Update GITHUB_REPO in version.py first.")
    return GITHUB_REPO


def _is_safe_url(url: str, repo: str) -> bool:
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return (parts.scheme == "https"
            and parts.hostname == "raw.githubusercontent.com"
            and parts.path.startswith(f"/{repo}/dlc/"))


def _fetch(url: str, repo: str) -> bytes:
    if not _is_safe_url(url, repo):
        raise DlcError("DLC download URL is not trusted — install aborted.")
    req = urllib.request.Request(url, headers={"User-Agent": "Tyoaikaweleho"})
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as r:
        return r.read()


def fetch_expected_hash(repo: str) -> str | None:
    """Return the published SHA-256 of the current DLC, or None when the
    dlc branch still uses the old version-only dlc_version.txt format."""
    url = f"https://raw.githubusercontent.com/{repo}/dlc/dlc_version.txt"
    fields = _fetch(url, repo).decode("utf-8", errors="replace").strip().split()
    if len(fields) < 2:
        return None
    token = fields[1].lower()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise DlcError("Published DLC checksum is malformed.")
    return token


def install() -> bool:
    """Download, verify, and atomically install the DLC.

    Returns True when the download was hash-verified, False when the
    publisher hasn't published a hash yet (old dlc_version.txt format).
    Raises DlcError on any failure — the previous DLC file (if any) is
    left untouched.
    """
    repo = _check_repo_configured()
    payload = _fetch(
        f"https://raw.githubusercontent.com/{repo}/dlc/{DLC_FILENAME}", repo)

    expected = fetch_expected_hash(repo)
    verified = expected is not None
    if verified:
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise DlcError(
                "DLC checksum mismatch — the download may be corrupted "
                "or tampered with. Install aborted.")

    dest = dlc_path()
    fd, tmp = tempfile.mkstemp(suffix=".py", dir=os.path.dirname(dest))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp, dest)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise DlcError(f"Could not write DLC file: {exc}") from exc
    return verified


def remove():
    """Delete the installed DLC file. Raises DlcError on failure."""
    try:
        os.remove(dlc_path())
    except OSError as exc:
        raise DlcError(f"Could not remove DLC file: {exc}") from exc
