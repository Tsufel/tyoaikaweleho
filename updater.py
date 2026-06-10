import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request

_DOWNLOAD_TIMEOUT = 30  # seconds


class UpdateError(Exception):
    """Raised when an update download fails validation."""


def cleanup_old_exe():
    """Remove the .old exe left behind by a previous update."""
    old = sys.executable + ".old"
    try:
        if os.path.exists(old):
            os.remove(old)
    except OSError:
        pass


def check_for_update(current_version: str, on_update_available):
    """Non-blocking background check against GitHub releases.

    Calls on_update_available(new_version, exe_url, sha256_url) on the
    calling thread if a newer .exe release is found. sha256_url is None
    when the release has no matching checksum asset. Network errors are
    silently ignored.
    """
    from version import GITHUB_REPO

    def _check():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "Tyoaikaweleho"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            latest = data["tag_name"].lstrip("v")
            if _is_newer(latest, current_version):
                assets = data.get("assets", [])
                for asset in assets:
                    if asset["name"].endswith(".exe"):
                        sha_url = next(
                            (a["browser_download_url"] for a in assets
                             if a["name"] == asset["name"] + ".sha256"),
                            None,
                        )
                        on_update_available(
                            latest, asset["browser_download_url"], sha_url)
                        return
        except Exception:
            pass

    threading.Thread(target=_check, daemon=True).start()


def check_for_dlc_update(current_version: str, on_update_available):
    """Non-blocking background check against the dlc branch's dlc_version.txt.

    Calls on_update_available(new_version) if a newer DLC version is published.
    Network errors are silently ignored.
    """
    from version import GITHUB_REPO

    def _check():
        try:
            url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/dlc/dlc_version.txt"
            req = urllib.request.Request(url, headers={"User-Agent": "Tyoaikaweleho"})
            with urllib.request.urlopen(req, timeout=5) as r:
                latest = r.read().decode().strip().split()[0]
            if _is_newer(latest, current_version):
                on_update_available(latest)
        except Exception:
            pass

    threading.Thread(target=_check, daemon=True).start()


def _is_newer(latest: str, current: str) -> bool:
    try:
        return (tuple(int(x) for x in latest.split("."))
                > tuple(int(x) for x in current.split(".")))
    except ValueError:
        return False


def _is_safe_download_url(url: str) -> bool:
    """Only allow release assets served over HTTPS from this app's own
    GitHub repository — anything else is rejected before download."""
    from version import GITHUB_REPO
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return (parts.scheme == "https"
            and parts.hostname == "github.com"
            and parts.path.startswith(f"/{GITHUB_REPO}/releases/download/"))


def _download_to(url: str, dest_path: str, timeout: int = _DOWNLOAD_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "Tyoaikaweleho"})
    with urllib.request.urlopen(req, timeout=timeout) as r, \
            open(dest_path, "wb") as f:
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)


def _fetch_expected_sha256(sha256_url: str) -> str:
    """Download a .sha256 asset and return the hex digest it contains."""
    req = urllib.request.Request(sha256_url, headers={"User-Agent": "Tyoaikaweleho"})
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as r:
        text = r.read().decode("utf-8", errors="replace")
    # Format: "<hex digest>" or "<hex digest>  <filename>"
    token = text.strip().split()[0].lower()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise UpdateError("Checksum file is malformed.")
    return token


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_update(download_url: str, sha256_url: str | None = None):
    """Download the new installer, verify it, and run it silently.

    Raises UpdateError if the URL is not a release asset of this app's
    repository or the checksum does not match. The Inno Setup installer
    handles overwriting the app, closing the running instance
    (/CLOSEAPPLICATIONS), and relaunching afterwards
    (/RESTARTAPPLICATIONS). No-op when running from Python source.
    """
    if not getattr(sys, "frozen", False):
        return

    if not _is_safe_download_url(download_url):
        raise UpdateError("Update download URL is not trusted — update aborted.")

    fd, tmp = tempfile.mkstemp(suffix=".exe")
    os.close(fd)
    try:
        _download_to(download_url, tmp)
        if sha256_url:
            if not _is_safe_download_url(sha256_url):
                raise UpdateError("Checksum URL is not trusted — update aborted.")
            expected = _fetch_expected_sha256(sha256_url)
            actual = _file_sha256(tmp)
            if expected != actual:
                raise UpdateError(
                    "Installer checksum mismatch — the download may be "
                    "corrupted or tampered with. Update aborted.")
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

    # /SILENT      — no wizard UI
    # /CLOSEAPPLICATIONS — gracefully closes the running instance before install
    # /RESTARTAPPLICATIONS — relaunches the app after install completes
    subprocess.Popen([tmp, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"])
    sys.exit(0)
