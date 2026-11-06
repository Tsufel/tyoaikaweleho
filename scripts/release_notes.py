"""Print the user-facing release notes for a version, from changelog.py.

    python scripts/release_notes.py 2.1.4         # Markdown, for the GitHub release
    python scripts/release_notes.py               # the version in version.py
    python scripts/release_notes.py 2.1.4 --out release-notes.md

Exits 1 (printing nothing to stdout) when changelog.py has no notes for the
version, so the release workflow stops instead of publishing empty notes."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bump_version import app_version, load_changelog  # noqa: E402


def notes(version: str) -> str | None:
    """The notes as a Markdown list, or None if there are none."""
    items = load_changelog().get(version)
    if not items:
        return None
    return "## What's new\n\n" + "\n".join(f"- {item}" for item in items) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("version", nargs="?",
                    help="X.Y.Z, with or without a leading v (default: version.py)")
    ap.add_argument("--out", help="write the notes to this file (UTF-8) instead of stdout")
    args = ap.parse_args(argv)
    version = (args.version or app_version() or "").lstrip("v")
    text = notes(version)
    if text is None:
        print(f"changelog.py has no notes for {version}.", file=sys.stderr)
        return 1
    if args.out:
        with open(args.out, "wb") as f:
            f.write(text.encode("utf-8"))
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
