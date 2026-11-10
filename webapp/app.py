"""pywebview shell: one hidden window, shown once the frontend says it is
ready (or after a watchdog), with the native title bar themed to match."""

import os
import shutil
import sys
import threading
import traceback
from datetime import datetime

import storage
from services import net
from utils import get_app_dir
from version import __version__
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
TITLE_TICK_S = 15.0

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


def title_for(start: datetime | None, now: datetime) -> str:
    """Window title: a running shift's elapsed H:MM first, so it shows on the
    taskbar button; just the app name while idle."""
    if start is None:
        return TITLE
    minutes = max(0, int((now - start).total_seconds() // 60))
    return f"{minutes // 60}:{minutes % 60:02d} · {TITLE}"


def frontend_index() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(get_app_dir(), "webui", "index.html")
    return os.path.join(get_app_dir(), "frontend", "dist", "index.html")


# The built-in web server (bottle) types each file by Python's mimetypes, which on
# Windows also reads HKEY_CLASSES_ROOT\.<ext>\Content Type: another program can
# leave .js or .css typed as text/plain (or worse), and WebView2 then refuses the
# file as a module script / stylesheet. These are what the bundle needs, fixed.
WEB_MIME_TYPES = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}


def register_web_mime_types() -> None:
    """Override whatever the registry says for the bundle's file types."""
    import mimetypes
    mimetypes.init()  # read the registry now, so it can't override these later
    for ext, mime in WEB_MIME_TYPES.items():
        mimetypes.add_type(mime, ext)


def serve_revalidated() -> None:
    """Keep the built-in web server's files out of WebView2's disk cache.

    pywebview sets no-cache headers on bottle.response, but bottle.static_file
    returns its own response whose headers replace them (HTTPResponse.apply),
    so only Last-Modified goes out. WebView2 then caches index.html for a while
    by heuristic, on an origin that is the same every launch
    (127.0.0.1:42001): after an update it kept running the old UI, whose lazy
    chunks (Stats, the pet sheet, achievements) the installer had deleted.

    no-store, not no-cache (2.1.8): WebView2 revalidates with If-Modified-Since
    only, and bottle answers 304 on the date alone, so a damaged cached copy
    was approved again on every load. A colleague's hidden Silver medals stayed
    broken images that way. Reading from disk on localhost costs nothing."""
    import bottle
    if getattr(bottle.static_file, "weleho_revalidate", False):
        return
    original = bottle.static_file

    def static_file(*args, **kwargs):
        resp = original(*args, **kwargs)
        resp.set_header("Cache-Control", "no-store")
        return resp

    static_file.weleho_revalidate = True
    bottle.static_file = static_file


# Connections the built-in web server lets wait. socketserver's default is 5,
# and every request is its own connection (HTTP/1.0): opening Achievements asks
# for ~20 medals at once, and Windows refuses what doesn't fit (a broken image).
LISTEN_BACKLOG = 64


def widen_listen_backlog() -> None:
    """Let more connections wait on the built-in web server (pywebview's
    server class derives from wsgiref's WSGIServer)."""
    from wsgiref.simple_server import WSGIServer
    WSGIServer.request_queue_size = max(WSGIServer.request_queue_size, LISTEN_BACKLOG)


# Which version's UI the WebView2 HTTP cache was filled by (in storage_path).
UI_VERSION_FILE = "weleho-ui-version.txt"


def web_cache_dir(storage_path: str) -> str:
    """WebView2's HTTP cache. Only this goes: Local Storage etc. are siblings."""
    return os.path.join(storage_path, "EBWebView", "Default", "Cache")


def clear_web_cache_on_update(version: str, storage_path: str) -> bool:
    """First launch of a new version: drop the HTTP cache, so no UI file an
    older version left fresh in it is used. Returns True if it was cleared.
    Tried again next launch if the cache can't be removed (a lingering
    WebView2 process holds it)."""
    marker = os.path.join(storage_path, UI_VERSION_FILE)
    try:
        with open(marker, encoding="utf-8") as f:
            if f.read().strip() == version:
                return False
    except OSError:
        pass
    cache = web_cache_dir(storage_path)
    shutil.rmtree(cache, ignore_errors=True)
    if os.path.exists(cache):
        storage.append_error_log(f"[app] could not clear the web cache: {cache}")
        return False
    os.makedirs(storage_path, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(version)
    return True


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
        self._placement = None
        if not smoke:
            try:
                self._placement = storage.get_window_placement()
            except (OSError, ValueError) as exc:
                # data.json unreadable: open at the default size; the UI
                # reports the problem once it has loaded
                storage.append_error_log(f"[app] window placement unreadable: {exc}")
        self._reveal_lock = threading.Lock()
        self._revealed = False
        self._close_guard = False
        self._quitting = False
        self.ready = threading.Event()
        self.renderer_ok = True
        self._title_stop = threading.Event()

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
        self._title_stop.set()
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
        self._title_stop.set()
        window = self.window
        if window is not None:
            threading.Timer(_QUIT_DELAY_S, window.destroy).start()

    # helpers ---------------------------------------------------------

    def _title_bar(self, dark: bool):
        win32.set_title_bar(self._hwnd, dark, BG_DARK if dark else BG_LIGHT,
                            TEXT_DARK if dark else TEXT_LIGHT)

    def title_loop(self, clock=datetime.now):
        """Light ticker: the running shift's elapsed time in the window title.
        Reads the timer only (no disk); sets the title only when it changes."""
        shown = TITLE
        while not self._quitting:
            try:
                title = title_for(self._c.running_start(), clock())
                if title != shown and self.window is not None:
                    self.window.set_title(title)
                    shown = title
            except Exception:
                storage.append_error_log("[app] window title\n" + traceback.format_exc())
                return
            if self._title_stop.wait(TITLE_TICK_S):
                return

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

    try:
        appearance = "System" if smoke else storage.get_appearance_mode()
    except (OSError, ValueError):
        # data.json unreadable: open anyway, the UI shows what went wrong
        appearance = "System"
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
            elif not net.has_bundled_roots():
                _say("smoke-test: certifi's cacert.pem is missing (update "
                     "checks would fail on PCs without GitHub's root)")
                outcome["code"] = 1
            else:
                _say("smoke-test: ok")
            shell.quit()
            return
        handle = win32.create_activate_event()
        if handle:
            threading.Thread(target=shell.activation_loop, args=(handle,),
                             name="weleho-activate", daemon=True).start()
        threading.Thread(target=shell.title_loop, name="weleho-title",
                         daemon=True).start()
        watchdog = threading.Timer(REVEAL_WATCHDOG_S, shell.show)
        watchdog.daemon = True
        watchdog.start()
        try:
            api._start_background_checks()
        except Exception:
            storage.append_error_log("[app] background checks\n" + traceback.format_exc())

    icon = os.path.join(get_app_dir(), "icon.ico")
    try:
        register_web_mime_types()
        serve_revalidated()
        widen_listen_backlog()
        if not dev_url and not smoke:
            clear_web_cache_on_update(__version__, webview_storage_path())
    except Exception:
        storage.append_error_log("[app] web server setup\n" + traceback.format_exc())
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
