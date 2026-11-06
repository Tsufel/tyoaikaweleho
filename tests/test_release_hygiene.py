"""The version is written in several files; they must agree, and
scripts/bump_version.py / scripts/release_notes.py must keep working."""

import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import bump_version  # noqa: E402
import release_notes  # noqa: E402
from version import __version__  # noqa: E402

_FILES = ("version.py", "changelog.py", "frontend/package.json", "frontend/package-lock.json")


def _ver(v):
    return tuple(int(p) for p in v.split("."))


# ── the repo as it is ────────────────────────────────────────────────────────

def test_every_place_has_the_same_version():
    found = bump_version.current_versions()
    assert set(found.values()) == {__version__}, (
        f"{found}\nrun: python scripts/bump_version.py {__version__}")


def test_the_current_version_has_release_notes():
    items = bump_version.load_changelog()[__version__]
    assert items, f"write the notes for {__version__} in changelog.py"
    assert all(isinstance(i, str) and i.strip() for i in items)


def test_changelog_is_newest_first():
    versions = bump_version.changelog_versions()
    assert versions == sorted(versions, key=_ver, reverse=True)


def test_check_passes_on_the_repo(capsys):
    assert bump_version.main(["--check"]) == 0
    assert __version__ in capsys.readouterr().out


def test_release_workflow_uses_the_changelog_notes():
    with open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8") as f:
        wf = f.read()
    assert "scripts/release_notes.py" in wf and "--notes-file release-notes.md" in wf
    assert "scripts/bump_version.py --check" in wf


# ── bump_version on a copy ───────────────────────────────────────────────────

@pytest.fixture()
def repo(tmp_path, monkeypatch):
    for rel in _FILES:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, rel), dst)
    monkeypatch.setattr(bump_version, "ROOT", str(tmp_path))
    return tmp_path


def _bytes(repo, rel):
    return (repo / rel).read_bytes()


def test_bump_sets_every_place(repo):
    bump_version.bump("9.8.7")
    found = bump_version.current_versions()
    assert set(found.values()) == {"9.8.7"}, found
    assert bump_version.load_changelog()["9.8.7"] == []
    assert bump_version.changelog_versions()[0] == "9.8.7"
    # the old notes are untouched
    assert bump_version.load_changelog()[__version__] == \
        bump_version.load_changelog(open(os.path.join(ROOT, "changelog.py"),
                                         encoding="utf-8").read())[__version__]


def test_bump_changes_only_the_version_lines(repo):
    before = {rel: _bytes(repo, rel) for rel in _FILES}
    bump_version.bump("9.8.7")
    for rel in ("version.py", "frontend/package.json", "frontend/package-lock.json"):
        old, new = before[rel].split(b"\n"), _bytes(repo, rel).split(b"\n")
        assert len(old) == len(new), rel
        changed = [(a, b) for a, b in zip(old, new) if a != b]
        assert changed and all(a.replace(__version__.encode(), b"9.8.7") == b
                               for a, b in changed), rel
    lock = json.loads(_bytes(repo, "frontend/package-lock.json"))
    assert lock["version"] == lock["packages"][""]["version"] == "9.8.7"
    # line ends are kept
    for rel in _FILES:
        assert (b"\r\n" in before[rel]) == (b"\r\n" in _bytes(repo, rel)), rel


def test_bump_twice_adds_one_changelog_entry(repo):
    bump_version.bump("9.8.7")
    once = _bytes(repo, "changelog.py")
    bump_version.bump("9.8.7")
    assert _bytes(repo, "changelog.py") == once


def test_bump_to_an_existing_version_keeps_its_notes(repo):
    before = _bytes(repo, "changelog.py")
    bump_version.bump(__version__)
    assert _bytes(repo, "changelog.py") == before


@pytest.mark.parametrize("bad", ["2.1", "v2.1.5", "2.1.5-beta", ""])
def test_bump_rejects_a_bad_version(repo, bad):
    before = {rel: _bytes(repo, rel) for rel in _FILES}
    with pytest.raises(SystemExit):
        bump_version.bump(bad)
    assert before == {rel: _bytes(repo, rel) for rel in _FILES}


def test_check_fails_when_a_place_disagrees(repo, capsys):
    pkg = repo / "frontend" / "package.json"
    pkg.write_bytes(pkg.read_bytes().replace(__version__.encode(), b"0.0.1", 1))
    assert bump_version.main(["--check"]) == 1
    assert "disagree" in capsys.readouterr().err


# ── release_notes ────────────────────────────────────────────────────────────

def test_notes_are_a_markdown_list_of_the_changelog_items():
    text = release_notes.notes(__version__)
    items = bump_version.load_changelog()[__version__]
    assert text.splitlines()[2:] == [f"- {i}" for i in items]


def test_notes_for_the_default_version_and_a_v_tag(capsysbinary):
    assert release_notes.main([]) == 0
    default = capsysbinary.readouterr().out
    assert release_notes.main([f"v{__version__}"]) == 0
    assert capsysbinary.readouterr().out == default
    assert default.decode("utf-8") == release_notes.notes(__version__)


def test_notes_to_a_file(tmp_path):
    out = tmp_path / "notes.md"
    assert release_notes.main([__version__, "--out", str(out)]) == 0
    assert out.read_bytes().decode("utf-8") == release_notes.notes(__version__)


def test_no_notes_is_an_error(capsysbinary):
    assert release_notes.main(["0.0.1"]) == 1
    captured = capsysbinary.readouterr()
    assert captured.out == b""
    assert b"no notes for 0.0.1" in captured.err
