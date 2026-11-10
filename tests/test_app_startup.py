"""webapp.app startup reads data.json before the window exists: an
unreadable file must not crash it (the UI reports the problem instead)."""
import pytest

import storage
import webapp.app as app


def _corrupt(*a, **k):
    raise storage.DataFileCorrupt("damaged")


def _locked(*a, **k):
    raise PermissionError(13, "locked")


@pytest.mark.parametrize("fail", [_corrupt, _locked])
def test_shell_opens_when_placement_unreadable(tmp_storage, monkeypatch, fail):
    monkeypatch.setattr(storage, "get_window_placement", fail)
    shell = app._Shell(controller=None, bus=None, smoke=False, dark=False)
    assert shell._placement is None
    assert "window placement unreadable" in (tmp_storage / "error.log").read_text(encoding="utf-8")


def test_shell_reads_placement(tmp_storage, monkeypatch):
    monkeypatch.setattr(storage, "get_window_placement", lambda: {"x": 1})
    assert app._Shell(controller=None, bus=None, smoke=False, dark=False)._placement == {"x": 1}


# ── window title ticker ──────────────────────────────────────────────────────

def test_title_for_shows_elapsed_while_running():
    from datetime import datetime
    now = datetime(2026, 9, 23, 10, 0, 0)
    assert app.title_for(None, now) == app.TITLE
    assert app.title_for(datetime(2026, 9, 23, 8, 55, 30), now) == f"1:04 · {app.TITLE}"
    assert app.title_for(datetime(2026, 9, 22, 9, 0, 0), now) == f"25:00 · {app.TITLE}"
    assert app.title_for(datetime(2026, 9, 23, 10, 5, 0), now) == f"0:00 · {app.TITLE}"


class _Ctrl:
    def __init__(self, start):
        self.start = start

    def running_start(self):
        return self.start


class _Win:
    def __init__(self):
        self.titles = []

    def set_title(self, t):
        self.titles.append(t)


def test_title_loop_sets_changes_only_and_stops(monkeypatch):
    from datetime import datetime
    now = datetime(2026, 9, 23, 10, 0, 0)
    ctrl = _Ctrl(datetime(2026, 9, 23, 9, 0, 0))
    shell = app._Shell(controller=ctrl, bus=None, smoke=True, dark=False)
    shell.window = _Win()
    ticks = iter([False, False, True])
    waits = []

    def wait(timeout):
        waits.append(timeout)
        if len(waits) == 2:
            ctrl.start = None  # shift stopped
        return next(ticks)

    monkeypatch.setattr(shell._title_stop, "wait", wait)
    shell.title_loop(clock=lambda: now)
    assert shell.window.titles == [f"1:00 · {app.TITLE}", app.TITLE]
    assert waits == [app.TITLE_TICK_S] * 3


def test_title_loop_logs_and_ends_on_failure(tmp_storage):
    class Broken:
        def running_start(self):
            raise RuntimeError("boom")

    shell = app._Shell(controller=Broken(), bus=None, smoke=True, dark=False)
    shell.window = _Win()
    shell.title_loop()
    assert "window title" in (tmp_storage / "error.log").read_text(encoding="utf-8")



# ── MIME types for the built-in web server ───────────────────────────────────
@pytest.fixture
def mime_db(monkeypatch):
    """A fresh mimetypes database; the process-wide one is put back after."""
    import mimetypes
    # init() builds a new database and rebinds these, so restoring them is enough
    for name in ("_db", "inited", "types_map", "common_types", "suffix_map", "encodings_map"):
        monkeypatch.setattr(mimetypes, name, getattr(mimetypes, name))
    monkeypatch.setattr(mimetypes, "_db", None)
    return mimetypes


def test_web_mime_types_override_a_bad_registry(mime_db, monkeypatch):
    # Another program left .js and .css typed as text/plain in HKCR, and .webp
    # untyped: the lazy Stats / Pet / Achievements chunks then can't load.
    def bad_registry(self, strict=True):
        self.add_type("text/plain", ".js", strict)
        self.add_type("text/plain", ".css", strict)
    monkeypatch.setattr(mime_db.MimeTypes, "read_windows_registry", bad_registry, raising=False)
    mime_db.init()
    assert mime_db.guess_type("x.css")[0] == "text/plain"  # the bad registry took

    app.register_web_mime_types()
    for ext, mime in app.WEB_MIME_TYPES.items():
        assert mime_db.guess_type("assets/StatsView-abc" + ext)[0] == mime, ext


def test_bottle_serves_bundle_types(mime_db, tmp_path):
    import bottle
    app.register_web_mime_types()
    for name in ("StatsView-abc.js", "StatsView-abc.css", "medal.webp", "inter.woff2"):
        (tmp_path / name).write_bytes(b"x")
    got = {n: bottle.static_file(n, root=str(tmp_path)).headers["Content-Type"].split(";")[0]
           for n in ("StatsView-abc.js", "StatsView-abc.css", "medal.webp", "inter.woff2")}
    assert got == {"StatsView-abc.js": "text/javascript", "StatsView-abc.css": "text/css",
                   "medal.webp": "image/webp", "inter.woff2": "font/woff2"}


# ── the UI is never served stale after an update ─────────────────────────────
# 2.1.6 "Stats, Pet and Achievements won't open, restarting doesn't help":
# pywebview's no-cache headers were dropped, so WebView2 kept the old UI cached
# for hours on the fixed 127.0.0.1:42001 origin, and that UI asked for lazy
# chunks the update had deleted.

def _get(url, headers=None):
    import time
    import urllib.error
    import urllib.request
    for _ in range(50):  # the server thread may not be listening yet
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}))
        except urllib.error.HTTPError as e:
            return e
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"no answer from {url}")


def test_real_web_server_serves_ui_revalidated(monkeypatch, tmp_path):
    import bottle
    from wsgiref.simple_server import WSGIServer
    from webview.http import BottleServer
    monkeypatch.setattr(bottle, "static_file", bottle.static_file)  # put back after
    monkeypatch.setattr(BottleServer, "common_path", None, raising=False)
    monkeypatch.setattr(WSGIServer, "request_queue_size", WSGIServer.request_queue_size)
    # (the daemon server thread itself lives on until the test run ends)
    app.serve_revalidated()
    wrapped = bottle.static_file
    app.serve_revalidated()
    assert bottle.static_file is wrapped  # wraps once only
    app.widen_listen_backlog()

    (tmp_path / "index.html").write_text("<p>ui</p>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "hidden_silver-x.webp").write_bytes(b"RIFF" + bytes(4) + b"WEBPmedal")
    addr, _, _ = BottleServer.start_server([str(tmp_path / "index.html")], None)
    r = _get(addr + "index.html")
    assert r.status == 200
    # 2.1.7: hidden Silver medals stayed broken images. With no-cache, WebView2
    # revalidated a damaged cached copy (bottle says 304 on the date alone) and
    # kept using it. no-store keeps every UI file out of the disk cache.
    assert r.headers["Cache-Control"] == "no-store"
    assert _get(addr + "assets/StatsView-gone.js").status == 404


def test_real_web_server_answers_a_burst_of_medals(monkeypatch, tmp_path):
    """Opening Achievements asks for ~20 medals at once, each on its own
    connection; socketserver's backlog of 5 lets Windows refuse some under load
    (a broken image). A medal's retry URL (?r=...) serves the same file."""
    from concurrent.futures import ThreadPoolExecutor
    from wsgiref.simple_server import WSGIServer
    from webview.http import BottleServer
    monkeypatch.setattr(BottleServer, "common_path", None, raising=False)
    monkeypatch.setattr(WSGIServer, "request_queue_size", 5)
    app.register_web_mime_types()
    app.widen_listen_backlog()
    assert WSGIServer.request_queue_size == app.LISTEN_BACKLOG >= 64
    app.widen_listen_backlog()
    assert WSGIServer.request_queue_size == app.LISTEN_BACKLOG  # never shrinks or grows

    medal = b"RIFF" + bytes(4) + b"WEBP" + bytes(range(256)) * 160  # ~40 KB, like a medal
    (tmp_path / "index.html").write_text("<p>ui</p>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "hidden_silver-x.webp").write_bytes(medal)
    addr, _, _ = BottleServer.start_server([str(tmp_path / "index.html")], None)
    assert _get(addr + "index.html").status == 200  # listening

    def fetch(i):
        r = _get(addr + f"assets/hidden_silver-x.webp?r={i}")
        return r.status, r.headers["Content-Type"], r.read()

    with ThreadPoolExecutor(max_workers=40) as pool:
        got = list(pool.map(fetch, range(80)))
    assert got == [(200, "image/webp", medal)] * 80


def _webview_dirs(root):
    default = root / "EBWebView" / "Default"
    (default / "Cache" / "Cache_Data").mkdir(parents=True)
    (default / "Cache" / "Cache_Data" / "index.js").write_text("old ui", encoding="utf-8")
    (default / "Local Storage").mkdir()
    (default / "Local Storage" / "leveldb").write_text("prefs", encoding="utf-8")
    return default


def test_update_clears_only_the_http_cache(tmp_path):
    default = _webview_dirs(tmp_path)
    assert app.clear_web_cache_on_update("2.1.7", str(tmp_path)) is True
    assert not (default / "Cache").exists()
    assert (default / "Local Storage" / "leveldb").read_text(encoding="utf-8") == "prefs"
    assert (tmp_path / app.UI_VERSION_FILE).read_text(encoding="utf-8") == "2.1.7"


def test_same_version_keeps_the_cache(tmp_path):
    default = _webview_dirs(tmp_path)
    (tmp_path / app.UI_VERSION_FILE).write_text("2.1.7\n", encoding="utf-8")
    assert app.clear_web_cache_on_update("2.1.7", str(tmp_path)) is False
    assert (default / "Cache" / "Cache_Data" / "index.js").exists()
    # the next update clears it again
    assert app.clear_web_cache_on_update("2.1.8", str(tmp_path)) is True
    assert not (default / "Cache").exists()


def test_first_launch_without_webview_dirs(tmp_path):
    root = tmp_path / "WebView2"
    assert app.clear_web_cache_on_update("2.1.7", str(root)) is True
    assert (root / app.UI_VERSION_FILE).read_text(encoding="utf-8") == "2.1.7"


def test_locked_cache_is_retried_next_launch(tmp_storage, tmp_path, monkeypatch):
    import shutil
    default = _webview_dirs(tmp_path)
    held = [True]  # a lingering WebView2 process holds the cache
    real = shutil.rmtree
    monkeypatch.setattr(app.shutil, "rmtree", lambda *a, **k: None if held[0] else real(*a, **k))
    assert app.clear_web_cache_on_update("2.1.7", str(tmp_path)) is False
    assert not (tmp_path / app.UI_VERSION_FILE).exists()
    assert "could not clear the web cache" in (tmp_storage / "error.log").read_text(encoding="utf-8")
    held[0] = False
    assert app.clear_web_cache_on_update("2.1.7", str(tmp_path)) is True
    assert not (default / "Cache").exists()


class _Event:
    def __iadd__(self, fn):
        return self


class _StubWindow:
    def __init__(self):
        from types import SimpleNamespace
        self.events = SimpleNamespace(**{n: _Event() for n in (
            "initialized", "before_show", "closing", "closed",
            "shown", "minimized", "maximized", "restored")})


@pytest.mark.parametrize("dev_url, smoke, clears", [
    (None, False, True),                       # the installed app
    ("http://localhost:5173", False, False),   # npm run dev: no cache of ours
    (None, True, False),                       # smoke test: a temp profile
])
def test_run_sets_up_the_web_server_before_start(tmp_storage, monkeypatch, tmp_path,
                                                 dev_url, smoke, clears):
    import bottle
    import webview
    monkeypatch.setattr(bottle, "static_file", bottle.static_file)  # put back after
    index = tmp_path / "index.html"
    index.write_text("<p>ui</p>", encoding="utf-8")
    monkeypatch.setattr(app.win32, "webview2_version", lambda: "130.0")
    monkeypatch.setattr(app.win32, "message_box", lambda *a, **k: None)
    monkeypatch.setattr(app, "frontend_index", lambda: str(index))
    monkeypatch.setattr(app, "_say", lambda *a, **k: None)
    monkeypatch.setattr(webview, "create_window", lambda *a, **k: _StubWindow())
    cleared = []
    monkeypatch.setattr(app, "clear_web_cache_on_update", lambda *a: cleared.append(a))
    seen = {}

    from wsgiref.simple_server import WSGIServer
    monkeypatch.setattr(WSGIServer, "request_queue_size", 5)

    def start(*a, **k):  # the window would open here
        seen["revalidated"] = getattr(bottle.static_file, "weleho_revalidate", False)
        seen["backlog"] = WSGIServer.request_queue_size
        seen["cleared"] = list(cleared)
        seen["storage_path"] = k["storage_path"]

    monkeypatch.setattr(webview, "start", start)
    app.run(dev_url=dev_url, smoke=smoke)
    assert seen["revalidated"] is True
    assert seen["backlog"] == app.LISTEN_BACKLOG
    assert seen["cleared"] == ([(app.__version__, seen["storage_path"])] if clears else [])
