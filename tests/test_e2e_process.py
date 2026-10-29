"""End-to-end crash recovery across real processes.

Process A builds the real Api/ShiftController, starts a shift and dies with
os._exit(1) (no cleanup, no atexit). Process B starts fresh against the same
WELEHO_DATA_DIR and must surface and resolve the leftover session.json using
the confirm protocol from docs/V2_UI_API.md §3/§6."""
import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Shared prelude for process B: a real Api over a controller whose clock is
# shifted by OFFSET_S seconds, plus a helper to print the result as JSON.
_PRELUDE = """
import json, os, sys
from datetime import datetime, timedelta
from webapp.api import Api
from webapp.controller import ShiftController
OFFSET = timedelta(seconds=float(os.environ.get("OFFSET_S", "0")))
api = Api(controller=ShiftController(clock=lambda: datetime.now() + OFFSET))
out = {}
def done():
    print("@@" + json.dumps(out))
"""


def _run(tmp_path, body: str, offset_s: float = 0, expect_rc: int = 0) -> dict:
    env = {**os.environ, "WELEHO_DATA_DIR": str(tmp_path), "OFFSET_S": str(offset_s),
           "PYTHONIOENCODING": "utf-8"}
    script = _PRELUDE + textwrap.dedent(body)
    p = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert p.returncode == expect_rc, p.stderr
    line = next(l for l in p.stdout.splitlines() if l.startswith("@@"))
    return json.loads(line[2:])


_CRASH = """
r = api.timer_start("now", job_shift="Sales")
out["start"] = r
out["session_exists"] = os.path.exists(os.path.join(os.environ["WELEHO_DATA_DIR"], "session.json"))
done()
sys.stdout.flush()
os._exit(1)
"""


def _crash(tmp_path) -> dict:
    """Process A: start a shift and die mid-shift."""
    a = _run(tmp_path, _CRASH, expect_rc=1)
    assert a["start"]["status"] == "ok" and a["start"]["timer"]["running"]
    assert a["session_exists"]
    assert (tmp_path / "session.json").exists()
    return a["start"]["timer"]


def _age_session(tmp_path, hours: float) -> datetime:
    """Move the crashed session's start back by *hours*; returns the new start."""
    p = tmp_path / "session.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    start = datetime.fromisoformat(s["start"]).replace(microsecond=0) - timedelta(hours=hours)
    s["start"] = start.isoformat()
    p.write_text(json.dumps(s), encoding="utf-8")
    return start


def _entries(tmp_path) -> list[dict]:
    p = tmp_path / "data.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))["entries"]


# ── 1. crash → recovery → save ──────────────────────────────────────────────

def test_crash_then_recovery_saves(tmp_path):
    timer = _crash(tmp_path)
    assert _entries(tmp_path) == []

    b = _run(tmp_path, """
    boot = api.bootstrap()
    out["recovery"] = boot["data"]["recovery"]
    out["pending"] = boot["data"]["timer"]["recovery_pending"]
    out["blocked"] = api.timer_start("now")
    out["saved"] = api.recovery_resolve("save", out["recovery"]["suggested_end"])
    out["after"] = api.bootstrap()["data"]["recovery"]
    out["session_left"] = os.path.exists(os.path.join(os.environ["WELEHO_DATA_DIR"], "session.json"))
    done()
    """, offset_s=2 * 3600)

    rec = b["recovery"]
    assert rec is not None and b["pending"] is True
    assert rec["start_iso"] == timer["start_iso"] and rec["job_shift"] == "Sales"
    assert 119 <= rec["elapsed_minutes"] <= 121 and rec["over_limit"] is False
    assert b["blocked"]["error"]["code"] == "recovery_pending"

    saved = b["saved"]
    assert saved["status"] == "saved" and saved["recovery"] is None
    start = datetime.fromisoformat(timer["start_iso"])
    assert saved["entry"]["time_in"] == f"{start:%H:%M}"
    assert saved["entry"]["time_out"] == rec["suggested_end"]
    assert b["after"] is None and not b["session_left"]

    [e] = _entries(tmp_path)
    assert (e["date"], e["job_shift"], e["time_in"], e["time_out"]) == (
        f"{start:%Y-%m-%d}", "Sales", f"{start:%H:%M}", rec["suggested_end"])


def test_crash_then_resume_under_a_minute_is_discarded(tmp_path):
    _crash(tmp_path)
    b = _run(tmp_path, """
    out["resume"] = api.recovery_resolve("resume")
    out["stop"] = api.timer_stop()
    done()
    """)
    assert b["resume"]["status"] == "ok" and b["resume"]["timer"]["running"]
    assert b["stop"]["status"] == "discarded"
    assert _entries(tmp_path) == []
    assert not (tmp_path / "session.json").exists()


def test_crash_then_recovery_discard_needs_confirm(tmp_path):
    timer = _crash(tmp_path)
    b = _run(tmp_path, """
    first = api.recovery_resolve("discard")
    out["first"] = first
    tok = first["confirm"]["token"]
    out["stale"] = api.recovery_resolve("discard", confirm=[
        {"kind": "discard_shift", "choice": "discard", "token": "1999-01-01T00:00:00"}])
    out["final"] = api.recovery_resolve("discard", confirm=[
        {"kind": "discard_shift", "choice": "discard", "token": tok}])
    done()
    """, offset_s=3600)
    assert b["first"]["status"] == "needs_confirm"
    assert b["first"]["confirm"]["kind"] == "discard_shift"
    assert b["first"]["confirm"]["token"] == timer["start_iso"]
    assert b["stale"]["error"]["code"] == "stale" and b["stale"]["recovery"] is not None
    assert b["final"]["status"] == "discarded" and b["final"]["recovery"] is None
    assert _entries(tmp_path) == []
    assert not (tmp_path / "session.json").exists()


# ── 2. session aged 25 h → over_24h ─────────────────────────────────────────

_OVER_24H = """
rec = api.bootstrap()["data"]["recovery"]
out["recovery"] = rec
out["resume"] = api.recovery_resolve("resume")
first = api.timer_stop()
out["first"] = first
c = first["confirm"]
ans = [{"kind": "over_24h", "choice": CHOICE, "token": c["token"]}]
r = api.timer_stop(confirm=ans)
out["second"] = r
if r["status"] == "needs_confirm":
    ans.append({"kind": "discard_shift", "choice": "discard",
                "token": r["confirm"]["token"]})
    out["third"] = api.timer_stop(confirm=ans)
out["running_after"] = api.get_timer()["timer"]["running"]
out["session_left"] = os.path.exists(os.path.join(os.environ["WELEHO_DATA_DIR"], "session.json"))
done()
"""


@pytest.mark.parametrize("choice", ["save", "discard", "keep"])
def test_aged_25h_session_over_24h(tmp_path, choice):
    _crash(tmp_path)
    start = _age_session(tmp_path, 25)
    b = _run(tmp_path, _OVER_24H.replace("CHOICE", repr(choice)))

    rec = b["recovery"]
    assert rec["start_iso"] == start.isoformat() and rec["over_limit"] is True
    assert rec["suggested_end"] == f"{start + timedelta(hours=8):%H:%M}"
    assert b["resume"]["timer"]["running"]

    c = b["first"]["confirm"]
    assert b["first"]["status"] == "needs_confirm" and c["kind"] == "over_24h"
    assert [o["id"] for o in c["options"]] == ["save", "discard", "keep"]
    assert c["token"] == start.isoformat()
    capped = f"{start + timedelta(hours=8):%H:%M}"
    assert c["details"]["capped_end"] == capped
    assert c["details"]["elapsed_minutes"] >= 25 * 60

    if choice == "save":
        assert b["second"]["status"] == "saved"
        [e] = _entries(tmp_path)
        assert (e["time_in"], e["time_out"]) == (f"{start:%H:%M}", capped)
        assert e["date"] == f"{start:%Y-%m-%d}"
        assert not b["running_after"] and not b["session_left"]
    elif choice == "discard":
        assert b["second"]["status"] == "needs_confirm"
        assert b["second"]["confirm"]["kind"] == "discard_shift"
        assert b["third"]["status"] == "discarded"
        assert _entries(tmp_path) == []
        assert not b["running_after"] and not b["session_left"]
    else:
        assert b["second"]["status"] == "cancelled"
        assert _entries(tmp_path) == []
        assert b["running_after"] and b["session_left"]


# ── 3. session aged 15 h → long_shift ───────────────────────────────────────

def test_aged_15h_session_long_shift_confirm(tmp_path):
    _crash(tmp_path)
    start = _age_session(tmp_path, 15)
    b = _run(tmp_path, """
    out["resume"] = api.recovery_resolve("resume")
    first = api.timer_stop()
    out["first"] = first
    tok = first["confirm"]["token"]
    out["keep"] = api.timer_stop(confirm=[{"kind": "long_shift", "choice": "keep", "token": tok}])
    out["stale"] = api.timer_stop(confirm=[
        {"kind": "long_shift", "choice": "stop", "token": "2000-01-01T00:00:00"}])
    out["stop"] = api.timer_stop(confirm=[{"kind": "long_shift", "choice": "stop", "token": tok}])
    done()
    """)
    assert b["resume"]["timer"]["start_iso"] == start.isoformat()
    c = b["first"]["confirm"]
    assert b["first"]["status"] == "needs_confirm" and c["kind"] == "long_shift"
    assert c["token"] == start.isoformat()
    assert 15 * 60 <= c["details"]["elapsed_minutes"] < 24 * 60
    assert b["keep"]["status"] == "cancelled" and b["keep"]["timer"]["running"]
    assert b["stale"]["error"]["code"] == "stale" and b["stale"]["timer"]["running"]

    s = b["stop"]
    assert s["status"] == "saved" and not s["timer"]["running"]
    assert s["entry"]["time_in"] == f"{start:%H:%M}"
    assert s["entry"]["minutes"] >= 15 * 60
    [e] = _entries(tmp_path)
    assert e["time_in"] == f"{start:%H:%M}" and e["date"] == f"{start:%Y-%m-%d}"
    assert not (tmp_path / "session.json").exists()
