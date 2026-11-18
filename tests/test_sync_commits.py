from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codex_ads.sync import GENERATED_FILENAMES, _commit_and_push


SYNC_PATHS = [*(f"sync/generated/{name}" for name in GENERATED_FILENAMES), "sync/upstream-state.json"]


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    ).stdout


def make_repo(tmp_path: Path, existing_outputs: bool = True) -> Path:
    repo = tmp_path / "consumer"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.test")
    (repo / "sync" / "generated").mkdir(parents=True)
    for name in ("notes.txt", "sync/generated/local-note.txt"):
        (repo / name).write_text("Confirmed user work.\n")
    (repo / "sync" / "upstream-state.json").write_text('{"last_synced_sha": null}\n')
    if existing_outputs:
        for name in GENERATED_FILENAMES:
            (repo / "sync" / "generated" / name).write_text("Confirmed output.\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Initial consumer")
    return repo


@pytest.mark.parametrize("existing_outputs", [False, True])
@pytest.mark.parametrize("staged_path", ["notes.txt", "sync/generated/local-note.txt"])
def test_sync_commit_preserves_unrelated_index(
    tmp_path: Path, existing_outputs: bool, staged_path: str
) -> None:
    repo = make_repo(tmp_path, existing_outputs)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    (repo / staged_path).write_text("Staged user work.\n")
    git(repo, "add", staged_path)
    index_before = git(repo, "diff", "--cached", "--binary")
    (repo / "sync" / "generated" / "untracked-note.txt").write_text("Local note.\n")
    for name in SYNC_PATHS:
        (repo / name).write_text(f"Updated {name}.\n")

    _commit_and_push(repo, "Update upstream inventory", push=True)

    assert set(git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()) == set(SYNC_PATHS)
    assert git(repo, "diff", "--cached", "--binary") == index_before
    assert git(repo, "show", f"HEAD:{staged_path}") == "Confirmed user work.\n"
    assert git(remote, "rev-parse", "refs/heads/main") == git(repo, "rev-parse", "HEAD")
    assert (repo / "sync" / "generated" / "untracked-note.txt").read_text() == "Local note.\n"
    assert "sync/generated/untracked-note.txt" not in git(repo, "ls-files").splitlines()


def test_unrelated_changes_do_not_create_or_push_a_sync_commit(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    before = git(repo, "rev-parse", "HEAD")
    (repo / "notes.txt").write_text("Staged user work.\n")
    git(repo, "add", "notes.txt")
    (repo / "sync" / "generated" / "local-note.txt").write_text("Unstaged user work.\n")
    index_before = git(repo, "diff", "--cached", "--binary")

    # No origin is configured: an attempted push would also fail this control.
    _commit_and_push(repo, "No sync change", push=True)

    assert git(repo, "rev-parse", "HEAD") == before
    assert git(repo, "diff", "--cached", "--binary") == index_before
    assert (repo / "sync" / "generated" / "local-note.txt").read_text() == "Unstaged user work.\n"


def test_sync_commit_with_clean_index(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    target = repo / SYNC_PATHS[0]
    target.write_text("New inventory.\n")

    _commit_and_push(repo, "Update upstream inventory", push=False)

    assert git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() == [SYNC_PATHS[0]]
    assert git(repo, "show", f"HEAD:{SYNC_PATHS[0]}") == "New inventory.\n"
    assert git(repo, "status", "--porcelain") == ""
