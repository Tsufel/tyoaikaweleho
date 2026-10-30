"""The js_api object (window.pywebview.api). A thin layer over ShiftController
that adds native dialogs, window plumbing and events (docs/V2_UI_API.md §5).

pywebview exposes every public attribute it finds, and recurses into public
non-callable ones, so everything that is not an API method is _-prefixed."""

import functools
import os
import sys
import threading
import traceback

import storage
from version import __version__
from webapp import results as R
from webapp.controller import ShiftController

_EXCEL_TYPES = ("Excel files (*.xlsx;*.xls)", "All files (*.*)")
_EXPORT_TYPES = ("Excel workbook (*.xlsx)",)
_IMAGE_TYPES = ("Image files (*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.tif;*.webp)",
                "All files (*.*)")
_DIALOG_OPEN = 10
_DIALOG_SAVE = 30
_CLIENT_ERROR_MAX = 8000


def _guarded(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as exc:
            storage.append_error_log(f"[api] {func.__name__}\n{traceback.format_exc()}")
            return R.error("internal", f"Unexpected error: {exc}")
    return wrapper


class _NullShell:
    """Stands in for the window shell (webapp.app) in tests."""
    window = None

    def reveal(self):
        pass

    def save_placement(self):
        pass

    def apply_theme(self, appearance: str, dark: bool):
        pass

    def set_close_guard(self, enabled: bool):
        pass

    def quit(self):
        pass


class Api:
    def __init__(self, controller: ShiftController | None = None, bus=None,
                 shell=None, version: str = __version__,
                 frozen: bool | None = None, dev: bool = False):
        self._c = controller or ShiftController()
        self._bus = bus
        self._shell = shell or _NullShell()
        self._version = version
        self._frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
        self._dev = bool(dev)
        self._dialog_lock = threading.Lock()
        self._last_dir: str | None = None

    def _emit(self, name: str, payload=None):
        if self._bus is not None:
            self._bus.emit(name, payload)

    # ── native dialogs (never under the controller lock) ─────────

    def _dialog_dir(self) -> str:
        if self._last_dir and os.path.isdir(self._last_dir):
            return self._last_dir
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        return docs if os.path.isdir(docs) else os.path.expanduser("~")

    def _dialog(self, kind: int, file_types, multiple: bool = False,
                save_filename: str = "") -> list[str]:
        window = self._shell.window
        if window is None:
            return []
        with self._dialog_lock:
            picked = window.create_file_dialog(kind, self._dialog_dir(), multiple,
                                               save_filename, file_types)
        if not picked:
            return []
        if isinstance(picked, str):
            picked = [picked]
        paths = [str(p) for p in picked if p]
        if paths:
            self._last_dir = os.path.dirname(paths[0])
        return paths

    # ── app / lifecycle ──────────────────────────────────────────

    @_guarded
    def bootstrap(self):
        return self._c.bootstrap(self._version, self._frozen, self._dev)

    @_guarded
    def frontend_ready(self):
        self._shell.reveal()
        return R.ok()

    @_guarded
    def set_close_guard(self, enabled):
        self._shell.set_close_guard(bool(enabled))
        return R.ok()

    @_guarded
    def close_app(self, confirm=None):
        result = self._c.close_app(confirm)
        if result.get("quit"):
            if "timer" in result:
                self._emit("timer:changed", result["timer"])
            self._shell.save_placement()
            self._shell.quit()
        return result

    @_guarded
    def set_theme(self, appearance, dark):
        if appearance not in ("System", "Light", "Dark"):
            return R.invalid("appearance", "Unknown appearance mode.")
        self._shell.apply_theme(appearance, bool(dark))
        return R.ok()

    @_guarded
    def log_client_error(self, message, stack=None):
        text = str(message or "")[:_CLIENT_ERROR_MAX]
        if stack:
            text += "\n" + str(stack)[:_CLIENT_ERROR_MAX]
        storage.append_error_log(f"[frontend] {text}")
        return R.ok()

    @_guarded
    def open_shifts_file(self):
        path = self._c.ensure_shifts_file()
        try:
            os.startfile(path)
        except OSError as exc:
            return R.error("internal", f"Could not open:\n{path}\n\n{exc}")
        return R.ok()

    # ── timer ────────────────────────────────────────────────────

    @_guarded
    def get_timer(self):
        return self._c.get_timer()

    @_guarded
    def timer_start(self, mode, time=None, job_shift=None, confirm=None):
        return self._c.timer_start(mode, time, job_shift, confirm)

    @_guarded
    def timer_stop(self, source="button", confirm=None):
        return self._c.timer_stop(source or "button", confirm)

    @_guarded
    def timer_discard(self, confirm=None):
        return self._c.timer_discard(confirm)

    @_guarded
    def recovery_resolve(self, action, end=None, confirm=None):
        result = self._c.recovery_resolve(action, end, confirm)
        if result.get("status") == "saved":
            self._emit("data:changed", {"reason": "recovery"})
        return result

    # ── entries ──────────────────────────────────────────────────

    @_guarded
    def list_month(self, year, month):
        return self._c.list_month(year, month)

    @_guarded
    def get_entry(self, id):
        return self._c.get_entry(id)

    @_guarded
    def save_entry(self, draft, confirm=None):
        return self._c.save_entry(draft, confirm)

    @_guarded
    def update_entry_field(self, id, field, value, confirm=None):
        return self._c.update_entry_field(id, field, value, confirm)

    @_guarded
    def delete_entry(self, id, confirm=None):
        return self._c.delete_entry(id, confirm)

    @_guarded
    def restore_entry(self, entry):
        result = self._c.restore_entry(entry)
        if result.get("ok"):
            self._emit("data:changed", {"reason": "restore"})
        return result

    # ── shifts & settings ────────────────────────────────────────

    @_guarded
    def get_settings(self):
        return self._c.get_settings()

    @_guarded
    def save_settings(self, draft):
        return self._c.save_settings(draft)

    @_guarded
    def save_ui_prefs(self, prefs):
        return self._c.save_ui_prefs(prefs)

    @_guarded
    def add_job_shift(self, name):
        return self._c.add_job_shift(name)

    @_guarded
    def get_stats(self, start_iso, end_iso, granularity="day"):
        return self._c.get_stats(start_iso, end_iso, granularity or "day")

    @_guarded
    def get_achievements(self):
        return self._c.get_achievements()

    @_guarded
    def ack_achievements(self, ids):
        return self._c.ack_achievements(ids)

    @_guarded
    def get_pet_stats(self):
        return self._c.get_pet_stats()

    # ── import / export / OCR ────────────────────────────────────

    @_guarded
    def export_month(self, year, month):
        name = self._c.export_filename(year, month)
        picked = self._dialog(_DIALOG_SAVE, _EXPORT_TYPES, save_filename=name)
        if not picked:
            return R.cancelled()
        path = picked[0]
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        return self._c.export_month(year, month, path)

    @_guarded
    def import_excel(self):
        paths = self._dialog(_DIALOG_OPEN, _EXCEL_TYPES, multiple=True)
        result = self._c.import_excel(paths)
        if result.get("ok") and result.get("imported"):
            self._emit("data:changed", {"reason": "import"})
        return result

    @_guarded
    def ocr_pick_and_extract(self):
        status = self._c.dlc_status()
        if not status.get("ocr_available"):
            return R.error("dlc_unavailable", "The Image OCR DLC is not installed.")
        paths = self._dialog(_DIALOG_OPEN, _IMAGE_TYPES, multiple=True)
        return self._c.ocr_extract(paths)

    @_guarded
    def ocr_save(self, rows):
        result = self._c.ocr_save(rows)
        if result.get("ok") and result.get("status") != "cancelled":
            self._emit("data:changed", {"reason": "ocr"})
        return result

    # ── updates & DLC ────────────────────────────────────────────

    @_guarded
    def check_updates(self):
        result = self._c.check_updates(self._version)
        app = result.get("app") or {}
        if result.get("ok") and app.get("available"):
            self._emit("update:available", {"version": app.get("latest"),
                                            "current": self._version})
        return result

    @_guarded
    def open_download_page(self):
        """Releases page in the browser: the way out when an in-app update
        can't connect. Fixed URL, nothing comes from the page."""
        import updater
        url = updater.download_page_url()
        try:
            os.startfile(url)
        except OSError as exc:
            return R.error("internal", f"Could not open:\n{url}\n\n{exc}")
        return R.ok()

    @_guarded
    def install_update(self):
        pending = self._c.pending_update
        if self._frozen and pending is not None:
            self._shell.save_placement()
            self._emit("update:installing", {"version": pending[0]})
        result = self._c.install_update(self._frozen)
        if not result.get("ok") and result.get("error", {}).get("code") == "update_failed":
            self._emit("update:failed", {"message": result.get("message", "")})
        return result

    @_guarded
    def get_dlc_status(self):
        return self._c.get_dlc_status()

    @_guarded
    def dlc_install(self):
        result = self._c.dlc_install()
        if "dlc" in result:
            self._emit("dlc:status", result["dlc"])
        return result

    @_guarded
    def dlc_remove(self, confirm=None):
        result = self._c.dlc_remove(confirm)
        if result.get("status") != "needs_confirm" and "dlc" in result:
            self._emit("dlc:status", result["dlc"])
        return result

    # ── startup background checks (called by webapp.app) ─────────

    def _start_background_checks(self):
        import updater
        from services import dlc

        def on_update(version, url, sha_url=None):
            self._c.remember_update(version, url, sha_url)
            self._emit("update:available", {"version": version, "current": self._version})

        updater.check_for_update(self._version, on_update)
        try:
            st = dlc.load_status()
        except Exception:
            return
        if st.get("state") != "ok":
            return

        def on_dlc(version):
            self._c.dlc_update_version = version
            self._emit("dlc:update", {"version": version})
            try:
                self._emit("dlc:status", self._c.dlc_status())
            except Exception:
                storage.append_error_log("[api] dlc status\n" + traceback.format_exc())

        updater.check_for_dlc_update(st.get("version") or "0.0.0", on_dlc)
