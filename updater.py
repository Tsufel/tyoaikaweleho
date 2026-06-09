import json
import os
import subprocess
import sys
import threading
import urllib.request


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

    Calls on_update_available(new_version, download_url) on the calling thread
    if a newer .exe release is found. Network errors are silently ignored.
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
                for asset in data.get("assets", []):
                    if asset["name"].endswith(".exe"):
                        on_update_available(latest, asset["browser_download_url"])
                        return
        except Exception:
            pass

    threading.Thread(target=_check, daemon=True).start()


def _is_newer(latest: str, current: str) -> bool:
    try:
        return (tuple(int(x) for x in latest.split("."))
                > tuple(int(x) for x in current.split(".")))
    except ValueError:
        return False


def apply_update(download_url: str):
    """Download the new installer and run it silently.

    The Inno Setup installer handles overwriting the app, closing the running
    instance (/CLOSEAPPLICATIONS), and relaunching afterwards
    (/RESTARTAPPLICATIONS).  No-op when running from Python source.
    """
    if not getattr(sys, "frozen", False):
        return

    import tempfile
    tmp = tempfile.mktemp(suffix=".exe")
    urllib.request.urlretrieve(download_url, tmp)
    # /SILENT      — no wizard UI
    # /CLOSEAPPLICATIONS — gracefully closes the running instance before install
    # /RESTARTAPPLICATIONS — relaunches the app after install completes
    subprocess.Popen([tmp, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"])
    sys.exit(0)
