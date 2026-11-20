from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from codex_ads.sync import collect_upstream_snapshot, write_generated


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def make_upstream(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "upstream"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.test")
    git(root, "config", "core.quotePath", "true")
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "plugin.json").write_text('{"version": "1.0"}')
    (root / "README.md").write_text("Use `/ads audit`.\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "Initial upstream")
    return root, git(root, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "name",
    [
        "café.txt",
        'quote"name.txt',
        "tab\tname.txt",
        "line\nname.txt",
        "carriage\rreturn.txt",
        " leading and trailing .txt ",
        "ordinary.txt",
    ],
)
def test_snapshot_retains_exact_added_path(tmp_path: Path, name: str) -> None:
    root, previous = make_upstream(tmp_path)
    (root / name).write_text("New upstream content.\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "Add upstream file")
    current = git(root, "rev-parse", "HEAD")

    snapshot = collect_upstream_snapshot(root, previous, current)

    assert snapshot["changed_files"] == [f"A\t{name}"]
    generated = write_generated(tmp_path / "consumer", snapshot)
    assert json.loads(generated["inventory"].read_text())["changed_files"] == [f"A\t{name}"]


def test_snapshot_retains_both_renamed_paths(tmp_path: Path) -> None:
    root, _ = make_upstream(tmp_path)
    before, after = "café\tbefore.txt", "renamed\nafter.txt"
    (root / before).write_text("Unchanged content makes this an exact rename.\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "Add file to rename")
    previous = git(root, "rev-parse", "HEAD")
    (root / before).rename(root / after)
    git(root, "add", "-A")
    git(root, "commit", "-m", "Rename upstream file")
    current = git(root, "rev-parse", "HEAD")

    assert collect_upstream_snapshot(root, previous, current)["changed_files"] == [
        f"R100\t{before}\t{after}"
    ]


def test_snapshot_retains_modification_and_deletion_paths(tmp_path: Path) -> None:
    root, _ = make_upstream(tmp_path)
    modified, deleted = "modified\rname.txt", 'deleted"name.txt'
    for name in (modified, deleted):
        (root / name).write_text("Before.\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "Add upstream files")
    previous = git(root, "rev-parse", "HEAD")
    (root / modified).write_text("After.\n")
    (root / deleted).unlink()
    git(root, "add", "-A")
    git(root, "commit", "-m", "Modify and remove upstream files")
    current = git(root, "rev-parse", "HEAD")

    assert set(collect_upstream_snapshot(root, previous, current)["changed_files"]) == {
        f"M\t{modified}", f"D\t{deleted}"
    }


def test_snapshot_has_no_changes_at_same_revision(tmp_path: Path) -> None:
    root, current = make_upstream(tmp_path)
    assert collect_upstream_snapshot(root, current, current)["changed_files"] == []


@pytest.mark.skipif(os.name != "posix", reason="Non-UTF8 byte filenames require POSIX")
def test_snapshot_preserves_non_utf8_path_in_inventory(tmp_path: Path) -> None:
    root, previous = make_upstream(tmp_path)
    name = os.fsdecode(b"non-utf8-\xff.txt")
    (root / name).write_text("New upstream content.\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "Add non-UTF8 filename")
    current = git(root, "rev-parse", "HEAD")

    snapshot = collect_upstream_snapshot(root, previous, current)
    assert snapshot["changed_files"] == [f"A\t{name}"]
    generated = write_generated(tmp_path / "consumer", snapshot)
    recorded = json.loads(generated["inventory"].read_text())["changed_files"]
    assert recorded == [f"A\t{name}"]
    assert os.fsencode(recorded[0].split("\t", 1)[1]) == b"non-utf8-\xff.txt"
    assert "non-utf8-\\udcff.txt" in generated["report"].read_text()
