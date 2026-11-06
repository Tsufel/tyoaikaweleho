"""String literals Python sends to the page (event names, data:changed
reasons, error codes, confirm kinds and their option ids) must be ones
types.ts declares, and docs/V2_UI_API.md must list them. Read from the source
with ast, so a typo in a rarely-hit branch fails here instead of in the UI."""
import ast
import glob
import inspect
import os
import re

import pytest

from webapp.api import Api

ROOT = os.path.join(os.path.dirname(__file__), "..")
TYPES_TS = os.path.join(ROOT, "frontend", "src", "lib", "api", "types.ts")
API_DOC = os.path.join(ROOT, "docs", "V2_UI_API.md")

pytestmark = pytest.mark.skipif(not os.path.isfile(TYPES_TS), reason="frontend not present")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _calls(folders=("webapp", "services")):
    """Every ast.Call in the backend's API-facing packages, with its file."""
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(ROOT, folder, "*.py"))):
            tree = ast.parse(_read(path), path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    yield os.path.relpath(path, ROOT), node


def _func_name(call: ast.Call) -> str | None:
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _str(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _arg(call: ast.Call, index: int, keyword: str):
    for kw in call.keywords:
        if kw.arg == keyword:
            return kw.value
    return call.args[index] if len(call.args) > index else None


def _ts_block(header: str) -> str:
    m = re.search(rf"^export (?:interface|type) {header}\b[^{{=]*[{{=](.*?)^(?:\}}|$)",
                  _read(TYPES_TS), re.S | re.M)
    assert m, f"{header} not found in types.ts"
    return m.group(1)


def _ts_union(name: str) -> set[str]:
    return set(re.findall(r"'([^']*)'", _ts_block(name).split(";")[0]))


def _doc_section(start: str, end: str) -> str:
    doc = _read(API_DOC)
    return doc[doc.index(start):doc.index(end, doc.index(start))]


# ── events ───────────────────────────────────────────────────────

def _emitted() -> dict[str, list[ast.Call]]:
    found: dict[str, list[ast.Call]] = {}
    for _path, call in _calls(("webapp",)):
        if _func_name(call) in ("emit", "_emit") and call.args and _str(call.args[0]):
            found.setdefault(_str(call.args[0]), []).append(call)
    return found


def _event_map() -> dict[str, str]:
    return dict(re.findall(r"^  '([\w:]+)': (.*);$", _ts_block("EventMap"), re.M))


def test_emitted_events_are_the_event_map():
    emitted, declared = set(_emitted()), set(_event_map())
    assert emitted - declared == set(), f"emitted but not in EventMap: {emitted - declared}"
    assert declared - emitted == set(), f"in EventMap but never emitted: {declared - emitted}"


def test_events_are_documented():
    section = _doc_section("## 11. Events", "## 12.")
    missing = [n for n in _event_map() if f"`{n}`" not in section]
    assert missing == [], f"docs §11 omits {missing}"


def test_data_changed_reasons_are_declared():
    declared = set(re.findall(r"'(\w+)'", _event_map()["data:changed"]))
    sent = set()
    for call in _emitted()["data:changed"]:
        payload = call.args[1]
        assert isinstance(payload, ast.Dict), "data:changed payload must be a literal dict"
        for k, v in zip(payload.keys, payload.values):
            if _str(k) == "reason":
                sent.add(_str(v))
    assert None not in sent
    assert sent == declared


# ── error codes ──────────────────────────────────────────────────

def test_error_codes_are_declared_and_documented():
    declared = _ts_union("ErrorCode")
    used = {"stale"}  # R.stale()
    for path, call in _calls():
        if _func_name(call) == "error" and isinstance(call.func, ast.Attribute) \
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "R":
            code = _str(_arg(call, 0, "code"))
            assert code, f"{path}:{call.lineno}: R.error code must be a string literal"
            used.add(code)
    assert used - declared == set(), f"error codes missing from ErrorCode: {used - declared}"
    section = _doc_section("### Error codes", "## 3.")
    documented = set(re.findall(r"`(\w+)`", section))
    assert documented == declared, (f"docs §2 vs ErrorCode: only in docs "
                                    f"{documented - declared}, only in types.ts "
                                    f"{declared - documented}")


# ── confirm kinds ────────────────────────────────────────────────

def _confirm_choices() -> dict[str, set[str]]:
    rows = re.findall(r"^  (\w+): (.*);$", _ts_block("ConfirmChoices"), re.M)
    return {kind: set(re.findall(r"'(\w+)'", ids)) for kind, ids in rows}


def test_confirm_kinds_and_choices_match_types_ts():
    kinds = _ts_union("ConfirmKind")
    choices = _confirm_choices()
    assert set(choices) == kinds
    asked: dict[str, set[str]] = {}
    for path, call in _calls():
        if _func_name(call) != "needs_confirm":
            continue
        where = f"{path}:{call.lineno}"
        kind = _str(_arg(call, 0, "kind"))
        assert kind in kinds, f"{where}: confirm kind {kind!r} not in ConfirmKind"
        options = _arg(call, 3, "options")
        assert isinstance(options, ast.List), f"{where}: options must be a literal list"
        ids = {_str(o.args[0]) for o in options.elts
               if isinstance(o, ast.Call) and _func_name(o) == "opt"}
        assert len(ids) == len(options.elts), f"{where}: every option must be opt('id', ...)"
        assert ids <= choices[kind], f"{where}: {kind} options {ids - choices[kind]} undeclared"
        for key in ("default", "cancel"):
            value = _str(_arg(call, 4 if key == "default" else 5, key))
            assert value in ids, f"{where}: {key}={value!r} is not one of the options"
        asked.setdefault(kind, set()).update(ids)
    assert set(asked) == kinds, f"declared but never asked: {kinds - set(asked)}"
    for kind, ids in asked.items():
        assert ids == choices[kind], f"{kind}: ConfirmChoices lists unused {choices[kind] - ids}"


def test_confirm_kinds_are_documented():
    section = _doc_section("### Confirm kinds", "## 4.")
    missing = [k for k in _ts_union("ConfirmKind") if f"`{k}`" not in section]
    assert missing == [], f"docs §3 omits {missing}"


# ── methods ──────────────────────────────────────────────────────

def test_doc_method_tables_list_every_public_method():
    section = _doc_section("## 5. Methods", "## 6.")
    documented = set(re.findall(r"^\| `(\w+)\(", section, re.M))
    public = {n for n, _ in inspect.getmembers(Api, inspect.isfunction)
              if not n.startswith("_")}
    assert documented - public == set(), f"documented but not on Api: {documented - public}"
    assert public - documented == set(), f"Api methods missing from docs §5: {public - documented}"
