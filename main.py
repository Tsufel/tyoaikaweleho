import sys
import os

# When running as a frozen exe, make the exe's own directory importable
# so the optional image_ocr.py DLC can be found there.
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))


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
    import ctypes
    ERROR_ALREADY_EXISTS = 183
    handle = ctypes.windll.kernel32.CreateMutexW(
        None, False, "Tyoaikaweleho_SingleInstance_Mutex")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    globals()["_instance_mutex_handle"] = handle  # keep alive for process lifetime
    return True


import updater
updater.cleanup_old_exe()   # removes any leftover .old exe from a previous update

from ui.main_window import App


if __name__ == "__main__":
    if not _acquire_single_instance_lock():
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, "Tyoaikaweleho is already running.", "Tyoaikaweleho", 0x40)
        sys.exit(0)

    application = App()
    application.mainloop()
