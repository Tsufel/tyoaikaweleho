"""Uncaught exceptions reach error.log (the exe has no console)."""
import sys
import threading

import main
import storage


def _log():
    with open(storage.ERROR_LOG, encoding="utf-8") as f:
        return f.read()


def _hooks(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "__excepthook__", lambda *a: None)
    monkeypatch.setattr(threading, "__excepthook__", lambda a: None)
    main._install_crash_logging()


def test_main_thread_crash_is_logged(tmp_storage, monkeypatch):
    _hooks(monkeypatch)
    try:
        raise ValueError("kaboom")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    text = _log()
    assert "[main] uncaught exception" in text and "ValueError: kaboom" in text


def test_ctrl_c_is_not_logged(tmp_storage, monkeypatch):
    _hooks(monkeypatch)
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert not storage.os.path.exists(storage.ERROR_LOG)


def test_thread_crash_is_logged(tmp_storage, monkeypatch):
    _hooks(monkeypatch)

    def boom():
        raise RuntimeError("worker fell over")
    t = threading.Thread(target=boom, name="worker-1")
    t.start()
    t.join()
    text = _log()
    assert "[thread worker-1]" in text and "RuntimeError: worker fell over" in text


def test_error_log_survives_many_threads(tmp_storage, monkeypatch):
    monkeypatch.setattr(storage, "_ERROR_LOG_MAX", 2048)
    threads = [threading.Thread(target=lambda i=i: [storage.append_error_log(f"line {i}-{n}")
                                                    for n in range(20)])
               for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    text = _log()
    assert len(text.encode("utf-8")) < 4096
    # every surviving record is whole: a header followed by its own line
    blocks = [b for b in text.split("--- ") if b.strip()][1:]
    assert blocks and all(b.rstrip().split("\n")[-1].startswith("line ") for b in blocks)
