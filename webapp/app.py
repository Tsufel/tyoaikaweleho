"""pywebview shell: one hidden window, shown once the frontend says it is
ready (or after a watchdog), with the native title bar themed to match."""

import os
import sys
import threading
import traceback

import storage
from utils import get_app_dir
from webapp import win32
from webapp.api import Api
from webapp.controller import ShiftController
from webapp.events import EventBus

TITLE = "Työaikaweleho"
BG_DARK, BG_LIGHT = "#0b0b1a", "#f6f5fb"
TEXT_DARK, TEXT_LIGHT = "#ececf6", "#1b1a2e"
REVEAL_WATCHDOG_S = 6.0
SMOKE_TIMEOUT_S = 30.0
PLACEMENT_LOCK_TIMEOUT_S = 2.0
_QUIT_DELAY_S = 0.05
_HUNG_RENDERER_S = 5.0

WEBVIEW2_MISSING = (
    "Työaikaweleho needs the Microsoft Edge WebView2 Runtime, which was not "
    "found on this PC.\n\nInstall the Evergreen WebView2 Runtime from:\n"
    f"{win32.WEBVIEW2_DOWNLOAD_URL}\n\nthen start Työaikaweleho again.")


def _say(msg: str):
    """Console output for --smoke-test; the windowed exe has no streams."""
    stream = sys.stderr or sys.stdout
    if stream is not None:
        try:
            print(msg, file=stream, flush=True)
        except (OSError, ValueError):
            pass


def _system_dark() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return False
    return value == 0


def _is_dark(appearance: str) -> bool:
    if appearance == "Dark":
        return True
    if appearance == "Light":
        return False
    return _system_dark()


def frontend_index() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(get_app_dir(), "webui", "index.html")
    return os.path.join(get_app_dir(), "frontend", "dist", "index.html")


def webview_storage_path() -> str:
    override = os.environ.get(storage.DATA_DIR_ENV, "").strip()
    if override:
        return os.path.join(override, "WebView2")
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Tyoaikaweleho", "WebView2")


class _Shell:
    """Window plumbing the Api calls into. Runs on js_api worker threads,
    except the window event handlers noted below."""

    def __init__(self, controller: ShiftController, bus: EventBus, smoke: bool,
                 dark: bool):
        self.window = None
        self._c = controller
        self._bus = bus
        self._smoke = smoke
        self._dark = dark
        self._hwnd = None
        self._placement = None if smoke else storage.get_window_placement()
        self._reveal_lock = threading.Lock()
        self._revealed = False
        self._close_guard = False
        self._quitting = False
        self.ready = threading.Event()
        self.renderer_ok = True

    # window events ---------------------------------------------------

    def on_initialized(self, renderer):
        if renderer != "edgechromium":
            self.renderer_ok = False
            return False
        return None

    def on_before_show(self):
        # GUI thread, before the hidden create
        try:
            self._hwnd = int(self.window.native.Handle.ToInt64())
        except Exception:
            self._hwnd = None
        self._title_bar(self._dark)

    def on_closing(self):
        # GUI thread, synchronous: must not call evaluate_js or block long
        if self._quitting or self._smoke:
            return True
        if (self._close_guard and self._bus.ready and not self._system_close()
                and not self._bus.stalled(_HUNG_RENDERER_S)):
            self._bus.emit("close:requested")
            return False
        self.save_placement()
        self._quitting = True
        return True

    def _system_close(self) -> bool:
        """Windows shutdown/logoff, Restart Manager or Task Manager: never
        hold these up; session.json keeps a running shift for recovery."""
        try:
            import clr
            from System.Reflection import BindingFlags
            from System.Windows.Forms import CloseReason, Form
            prop = clr.GetClrType(Form).GetProperty(
                "CloseReason", BindingFlags.Instance | BindingFlags.NonPublic)
            reason = prop.GetValue(self.window.native)
            return reason in (CloseReason.WindowsShutDown, CloseReason.TaskManagerClosing)
        except Exception:
            return False

    def on_closed(self):
        self._bus.close()

    def on_visibility(self):
        if self._revealed:
            self._bus.emit("window:visibility", win32.window_state(self._hwnd))

    # Api hooks -------------------------------------------------------

    def reveal(self):
        """frontend_ready: start delivering events and show the window."""
        self._bus.set_ready()
        self.ready.set()
        if not self._smoke:
            self.show()

    def show(self):
        with self._reveal_lock:
            if self._revealed or self._quitting or self.window is None:
                return
            self._revealed = True
        rect, maximized = win32.restore_rect(self._placement)
        win32.set_normal_rect(self._hwnd, rect)
        if maximized:
            self.window.maximize()
        self.window.show()
        win32.bring_to_front(self._hwnd)

    def save_placement(self):
        if self._smoke or not self._revealed:
            return
        placement = win32.get_placement(self._hwnd)
        if placement is None:
            return
        lock = self._c._lock
        if not lock.acquire(timeout=PLACEMENT_LOCK_TIMEOUT_S):
            return
        try:
            storage.set_window_placement(placement)
        except Exception:
            storage.append_error_log("[app] save placement\n" + traceback.format_exc())
        finally:
            lock.release()

    def apply_theme(self, appearance: str, dark: bool):
        self._dark = bool(dark)
        self._title_bar(self._dark)

    def set_close_guard(self, enabled: bool):
        self._close_guard = bool(enabled)

    def quit(self):
        self._quitting = True
        window = self.window
        if window is not None:
            threading.Timer(_QUIT_DELAY_S, window.destroy).start()

    # helpers ---------------------------------------------------------

    def _title_bar(self, dark: bool):
        win32.set_title_bar(self._hwnd, dark, BG_DARK if dark else BG_LIGHT,
                            TEXT_DARK if dark else TEXT_LIGHT)

    def activation_loop(self, handle):
        while win32.wait_activate(handle):
            if self._quitting:
                return
            if self._revealed:
                win32.bring_to_front(self._hwnd)
                self._bus.emit("app:activate")
            else:
                self.show()


def run(dev_url: str | None = None, smoke: bool = False) -> int:
    import webview

    if win32.IS_WINDOWS and win32.webview2_version() is None:
        if smoke:
            _say("smoke-test: WebView2 Runtime not found")
        else:
            win32.message_box(WEBVIEW2_MISSING, TITLE, win32.MB_ICONERROR)
        return 2

    if dev_url:
        url = dev_url
    else:
        url = frontend_index()
        if not os.path.isfile(url):
            msg = f"The app's user interface is missing:\n{url}"
            if not getattr(sys, "frozen", False):
                msg += "\n\nBuild it first: cd frontend && npm ci && npm run build"
            if smoke:
                _say(f"smoke-test: {msg}")
            else:
                win32.message_box(msg, TITLE, win32.MB_ICONERROR)
            return 3

    appearance = "System" if smoke else storage.get_appearance_mode()
    dark = _is_dark(appearance)
    controller = ShiftController()
    bus = EventBus()
    shell = _Shell(controller, bus, smoke, dark)
    api = Api(controller, bus, shell, dev=bool(dev_url))

    window = webview.create_window(
        TITLE, url, js_api=api,
        width=win32.DEFAULT_SIZE[0], height=win32.DEFAULT_SIZE[1],
        min_size=win32.MIN_SIZE, hidden=True,
        background_color=BG_DARK if dark else BG_LIGHT,
        text_select=True, zoomable=False)
    if window is None:
        return 4
    shell.window = window
    bus.attach(window)
    window.events.initialized += shell.on_initialized
    window.events.before_show += shell.on_before_show
    window.events.closing += shell.on_closing
    window.events.closed += shell.on_closed
    for ev in (window.events.shown, window.events.minimized,
               window.events.maximized, window.events.restored):
        ev += shell.on_visibility

    outcome = {"code": 0}

    def started():
        bus.start()
        if smoke:
            if not shell.ready.wait(SMOKE_TIMEOUT_S):
                _say("smoke-test: frontend_ready was not called within "
                      f"{SMOKE_TIMEOUT_S:.0f} s")
                outcome["code"] = 1
            else:
                _say("smoke-test: ok")
            shell.quit()
            return
        handle = win32.create_activate_event()
        if handle:
            threading.Thread(target=shell.activation_loop, args=(handle,),
                             name="weleho-activate", daemon=True).start()
        watchdog = threading.Timer(REVEAL_WATCHDOG_S, shell.show)
        watchdog.daemon = True
        watchdog.start()
        try:
            api._start_background_checks()
        except Exception:
            storage.append_error_log("[app] background checks\n" + traceback.format_exc())

    icon = os.path.join(get_app_dir(), "icon.ico")
    try:
        webview.start(started, gui="edgechromium", debug=bool(dev_url),
                      http_server=not dev_url, private_mode=False,
                      storage_path=webview_storage_path(),
                      icon=icon if os.path.isfile(icon) else None)
    except Exception:
        storage.append_error_log("[app] webview.start\n" + traceback.format_exc())
        if smoke:
            _say(traceback.format_exc())
        else:
            win32.message_box(WEBVIEW2_MISSING, TITLE, win32.MB_ICONERROR)
        return 2
    finally:
        bus.close()

    if not shell.renderer_ok:
        if smoke:
            _say("smoke-test: WebView2 could not be loaded")
        else:
            win32.message_box(WEBVIEW2_MISSING, TITLE, win32.MB_ICONERROR)
        return 2
    return outcome["code"]
