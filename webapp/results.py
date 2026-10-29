"""Result envelopes, confirm requests and the shapes the JS API returns
(docs/V2_UI_API.md §2, §3, §8)."""
from dataclasses import asdict, is_dataclass
from datetime import date

from utils import entry_minutes, is_overnight, week_key


class Stale(Exception):
    """A confirm answer's token no longer matches the current state."""


def _result(ok: bool, status: str, message: str | None = None, **payload) -> dict:
    out = {"ok": ok, "status": status}
    if message:
        out["message"] = message
    out.update(payload)
    return out


def ok(message: str | None = None, **payload) -> dict:
    return _result(True, "ok", message, **payload)


def saved(message: str | None = None, **payload) -> dict:
    return _result(True, "saved", message, **payload)


def discarded(message: str | None = None, **payload) -> dict:
    return _result(True, "discarded", message, **payload)


def cancelled(message: str | None = None, **payload) -> dict:
    return _result(True, "cancelled", message, **payload)


def invalid(field: str, message: str, **payload) -> dict:
    return _result(False, "invalid", message, field=field, **payload)


def error(code: str, message: str, detail: str | None = None, **payload) -> dict:
    err = {"code": code, "message": message}
    if detail:
        err["detail"] = detail
    return _result(False, "error", message, error=err, **payload)


def stale(**payload) -> dict:
    return error("stale", "Things changed in the meantime — please try again.", **payload)


def opt(id: str, label: str, variant: str | None = None) -> dict:
    o = {"id": id, "label": label}
    if variant:
        o["variant"] = variant
    return o


def needs_confirm(kind: str, title: str, message: str, options: list[dict],
                  default: str, cancel: str, icon: str = "question",
                  token: str | None = None, details: dict | None = None,
                  **payload) -> dict:
    req = {"kind": kind, "title": title, "message": message, "options": options,
           "default": default, "cancel": cancel, "icon": icon}
    if token is not None:
        req["token"] = token
    if details:
        req["details"] = details
    return _result(False, "needs_confirm", None, confirm=req, **payload)


def answer(confirm, kind: str, token: str | None = None) -> str | None:
    """The latest choice given for *kind* in a confirm list, or None.
    Raises Stale when that answer carries a token other than *token*."""
    if not isinstance(confirm, (list, tuple)):
        return None
    for a in reversed(confirm):
        if isinstance(a, dict) and a.get("kind") == kind:
            given = a.get("token")
            if given is not None and token is not None and given != token:
                raise Stale(kind)
            choice = a.get("choice")
            return choice if isinstance(choice, str) else None
    return None


def work_entry_dict(entry) -> dict:
    d = asdict(entry) if is_dataclass(entry) else dict(entry)
    return {k: d.get(k, "") for k in ("id", "date", "job_shift", "time_in", "time_out")}


def entry_row(entry) -> dict:
    """WorkEntry + minutes/overnight/display fields (EntryRow)."""
    row = work_entry_dict(entry)
    t_in, t_out = row["time_in"], row["time_out"]
    closed = bool(t_in and t_out)
    overnight = closed and is_overnight(t_in, t_out)
    try:
        d = date.fromisoformat(row["date"])
        display_date = d.strftime("%a %d %b %Y")
        y, w = week_key(d)
        wk = f"{y}-W{w:02d}"
    except ValueError:
        display_date, wk = row["date"], ""
    row.update(
        minutes=entry_minutes(t_in, t_out) if closed else None,
        overnight=overnight,
        display_date=display_date,
        time_out_display=f"{t_out} +1" if overnight else t_out,
        week_key=wk,
    )
    return row


def describe(entry) -> str:
    """'on Tue 23 Sep, 09:00–17:00' (as ui/main_window._describe)."""
    d = work_entry_dict(entry)
    try:
        day = date.fromisoformat(d["date"]).strftime("%a %d %b")
    except ValueError:
        day = d["date"]
    return f"on {day}, {d['time_in']}–{d['time_out']}"


def money(x: float) -> float:
    return round(x, 2)
