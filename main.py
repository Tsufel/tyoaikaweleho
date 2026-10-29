import argparse
import os
import sys
import tempfile

# When running as a frozen exe, make the exe's own directory importable
# so the optional image_ocr.py DLC can be found there.
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))

DATA_DIR_ENV = "WELEHO_DATA_DIR"   # storage.DATA_DIR_ENV; read when storage is imported
DEV_URL = "http://localhost:5173/"


def _parse_args(argv=None):
    p = argparse.ArgumentParser(prog="Tyoaikaweleho", add_help=True)
    p.add_argument("--dev", nargs="?", const=DEV_URL, default=None, metavar="URL",
                   help=f"load the Vite dev server (default {DEV_URL}) with DevTools")
    p.add_argument("--smoke-test", action="store_true",
                   help="start hidden, wait for the UI to load, then exit")
    args, _unknown = p.parse_known_args(argv)
    return args


def _acquire_single_instance_lock():
    """Refuse to start a second instance on Windows.

    A stray second instance is the main reason the installer's
    CloseApplications step can fail to release _internal\\*.pyd/dll
    files during an update (Restart Manager closes one instance, the
    other keeps the handle open). Returns False if another instance
    already holds the mutex.
    """
    if os.name != "nt":
        return True
    from webapp import win32
    acquired, handle = win32.acquire_single_instance()
    globals()["_instance_mutex_handle"] = handle  # keep alive for process lifetime
    return acquired


def main(argv=None) -> int:
    args = _parse_args(argv)

    if args.smoke_test and not os.environ.get(DATA_DIR_ENV, "").strip():
        # a smoke run must never touch the real data
        os.environ[DATA_DIR_ENV] = tempfile.mkdtemp(prefix="weleho-smoke-")

    if not args.smoke_test and not _acquire_single_instance_lock():
        from webapp import win32
        if not win32.focus_existing():
            win32.message_box("Tyoaikaweleho is already running.", "Tyoaikaweleho",
                              win32.MB_ICONINFORMATION)
        return 0

    import updater
    if not args.smoke_test:
        updater.cleanup_old_exe()   # removes any leftover .old exe from a previous update

    from webapp.app import run
    return run(dev_url=args.dev, smoke=args.smoke_test)


if __name__ == "__main__":
    sys.exit(main())
