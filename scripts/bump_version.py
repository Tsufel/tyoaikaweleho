"""Set the app version everywhere it is written.

    python scripts/bump_version.py 2.1.5
    python scripts/bump_version.py --check      # exit 1 if the places disagree

Places (tests/test_release_hygiene.py keeps them in sync):
  version.py                   __version__
  frontend/package.json        "version"
  frontend/package-lock.json   "version" of the root and of packages[""]
  changelog.py                 newest entry (an empty one is added for a new
                               version: write the notes before tagging; the
                               tests fail while it is empty)

installer.iss gets the version from build.bat / the release workflow
(/DAppVersion=...), so it has nothing to bump.

Each file is edited in place with a narrow text replace, so its formatting
and line ends stay as they are."""

import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

_PY = "version.py"
_PKG = "frontend/package.json"
_LOCK = "frontend/package-lock.json"
_CHANGELOG = "changelog.py"

_PY_LINE = re.compile(r'^(__version__\s*=\s*")([^"]*)(")', re.M)
# the first "version" in package.json is the package's own
_PKG_LINE = re.compile(r'^(  "version":\s*")([^"]*)(")', re.M)
# package-lock: the root "version" (2 spaces) and packages[""] (6 spaces),
# both before any dependency is listed
_LOCK_ROOT = re.compile(r'^(  "version":\s*")([^"]*)(")', re.M)
_LOCK_PKG = re.compile(r'^(    "":\s*\{\s*\n(?:      .*\n)*?      "version":\s*")([^"]*)(")', re.M)
_CHANGELOG_START = re.compile(r"^(CHANGELOG[^=]*=\s*\{\r?\n)", re.M)


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "rb") as f:
        return f.read().decode("utf-8")


def _write(rel: str, text: str):
    with open(os.path.join(ROOT, rel), "wb") as f:
        f.write(text.encode("utf-8"))


def _ver_tuple(v: str) -> tuple:
    return tuple(int(p) for p in v.split("."))


def load_changelog(text: str | None = None) -> dict[str, list[str]]:
    """changelog.py's CHANGELOG dict, read without importing (running) it."""
    tree = ast.parse(text if text is not None else _read(_CHANGELOG))
    for node in tree.body:
        target = node.targets[0] if isinstance(node, ast.Assign) else getattr(node, "target", None)
        if isinstance(target, ast.Name) and target.id == "CHANGELOG":
            return ast.literal_eval(node.value)
    raise SystemExit(f"No CHANGELOG in {_CHANGELOG}")


def app_version() -> str | None:
    """The version in version.py."""
    m = _PY_LINE.search(_read(_PY))
    return m.group(2) if m else None


def changelog_versions(text: str | None = None) -> list[str]:
    """changelog.py's versions, in file order (newest first by convention)."""
    return list(load_changelog(text))


def current_versions() -> dict[str, str | None]:
    """{place: version written there} (None where it can't be found)."""
    lock_json = json.loads(_read(_LOCK))
    versions = changelog_versions()
    newest = max(versions, key=_ver_tuple) if versions else None
    return {
        _PY: app_version(),
        _PKG: json.loads(_read(_PKG)).get("version"),
        _LOCK + " (root)": lock_json.get("version"),
        _LOCK + ' (packages[""])': lock_json.get("packages", {}).get("", {}).get("version"),
        _CHANGELOG + " (newest entry)": newest,
    }


def _sub_once(pattern: re.Pattern, text: str, version: str, where: str) -> str:
    new, n = pattern.subn(lambda m: m.group(1) + version + m.group(3), text, count=1)
    if n != 1:
        raise SystemExit(f"Could not find the version in {where}")
    return new


def _add_changelog_entry(text: str, version: str) -> str:
    if version in changelog_versions(text):
        return text
    m = _CHANGELOG_START.search(text)
    if not m:
        raise SystemExit(f"Could not find the CHANGELOG dict in {_CHANGELOG}")
    nl = "\r\n" if "\r\n" in text else "\n"
    entry = f'    "{version}": [{nl}    ],{nl}'
    return text[:m.end()] + entry + text[m.end():]


def bump(version: str):
    if not VERSION_RE.fullmatch(version):
        raise SystemExit(f"Not a version: {version!r} (expected X.Y.Z)")
    # every file is worked out before any is written: all or nothing
    lock = _sub_once(_LOCK_ROOT, _read(_LOCK), version, _LOCK)
    new = {
        _PY: _sub_once(_PY_LINE, _read(_PY), version, _PY),
        _PKG: _sub_once(_PKG_LINE, _read(_PKG), version, _PKG),
        _LOCK: _sub_once(_LOCK_PKG, lock, version, _LOCK + ' packages[""]'),
        _CHANGELOG: _add_changelog_entry(_read(_CHANGELOG), version),
    }
    for rel, text in new.items():
        if text != _read(rel):
            _write(rel, text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("version", nargs="?", help="the new version, X.Y.Z")
    ap.add_argument("--check", action="store_true",
                    help="only report whether every place has the same version")
    args = ap.parse_args(argv)
    if args.check or not args.version:
        found = current_versions()
        for place, v in found.items():
            print(f"{v or '?':>10}  {place}")
        if len(set(found.values())) != 1:
            print("Versions disagree.", file=sys.stderr)
            return 1
        return 0
    bump(args.version)
    print(f"Version set to {args.version}. Next: write its notes in {_CHANGELOG}, "
          f"run the tests, commit, then tag v{args.version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
