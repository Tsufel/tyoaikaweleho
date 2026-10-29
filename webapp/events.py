"""Python → JS events. Everything that runs JS in the page goes through the
single pump thread here: evaluate_js waits on the GUI thread, so calling it
from a GUI event handler or under the controller lock can deadlock."""

import json
import queue
import threading
import time
import traceback

import storage

CHANNEL = "weleho"
_STOP = object()


class EventBus:
    def __init__(self, window=None):
        self._window = window
        self._queue: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._thread: threading.Thread | None = None
        self._delivering_since: float | None = None

    def attach(self, window):
        self._window = window

    @property
    def ready(self) -> bool:
        return self._ready.is_set() and not self._closed.is_set()

    def emit(self, name: str, payload=None):
        """Queue an event; delivered in order once the page is ready."""
        if self._closed.is_set():
            return
        self._queue.put((name, {} if payload is None else payload))

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._pump, name="weleho-events",
                                            daemon=True)
            self._thread.start()

    def stalled(self, seconds: float) -> bool:
        """True while one delivery has been stuck in evaluate_js for longer
        than `seconds` (the renderer is hung)."""
        since = self._delivering_since
        return since is not None and time.monotonic() - since > seconds

    def set_ready(self):
        self._ready.set()

    def close(self):
        self._closed.set()
        self._ready.set()
        self._queue.put(_STOP)

    @staticmethod
    def script(name: str, payload) -> str:
        detail = json.dumps({"name": name, "payload": payload}, ensure_ascii=True)
        return (f"window.dispatchEvent(new CustomEvent({json.dumps(CHANNEL)}, "
                f"{{detail: {detail}}}));")

    def _pump(self):
        self._ready.wait()
        while True:
            item = self._queue.get()
            if item is _STOP or self._closed.is_set():
                return
            name, payload = item
            try:
                script = self.script(name, payload)
            except (TypeError, ValueError):
                storage.append_error_log(f"[events] unserialisable payload for {name}\n"
                                         + traceback.format_exc())
                continue
            window = self._window
            if window is None:
                continue
            self._delivering_since = time.monotonic()
            try:
                window.evaluate_js(script)
            except Exception:
                if self._closed.is_set():
                    return
                storage.append_error_log(f"[events] could not deliver {name}\n"
                                         + traceback.format_exc())
            finally:
                self._delivering_since = None
