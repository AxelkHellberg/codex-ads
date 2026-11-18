from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from codex_ads.sync import sync_repo


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


def make_upstream(root: Path, updates: int, branch: str = "main") -> tuple[Path, str, str]:
    upstream = root / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "Test")
    git(upstream, "config", "user.email", "test@example.test")
    (upstream / ".claude-plugin").mkdir()
    (upstream / ".claude-plugin" / "plugin.json").write_text('{"version": "1.0"}')
    (upstream / "README.md").write_text("Use `/ads audit`.\n")
    (upstream / "removed.txt").write_text("removed after the checkpoint\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "Initial checkpoint")
    previous = git(upstream, "rev-parse", "HEAD")
    if branch != "main":
        git(upstream, "switch", "-c", branch)
    for index in range(updates):
        (upstream / "README.md").write_text(f"Use `/ads audit`.\nRevision {index}\n")
        if index == 0:
            (upstream / "removed.txt").unlink()
            (upstream / "added.txt").write_text("added since the checkpoint\n")
        git(upstream, "add", "-A")
        git(upstream, "commit", "-m", f"Update {index}")
    return upstream, previous, git(upstream, "rev-parse", "HEAD")


def make_consumer(root: Path, upstream: Path, previous: str, branch: str = "main") -> Path:
    repo = root / "consumer"
    (repo / "sync").mkdir(parents=True)
    (repo / "sync" / "upstream-map.yaml").write_text('{"rules": []}')
    (repo / "sync" / "upstream-state.json").write_text(
        json.dumps(
            {"upstream_repo": upstream.as_uri(), "tracked_branch": branch, "last_synced_sha": previous}
        )
    )
    return repo


@pytest.mark.parametrize("branch,updates", [("main", 1), ("main", 51), ("release", 51)])
def test_sync_retains_checkpoint_diff_across_shallow_history(
    tmp_path: Path, branch: str, updates: int
) -> None:
    upstream, previous, head = make_upstream(tmp_path, updates, branch)
    repo = make_consumer(tmp_path, upstream, previous, branch)

    assert sync_repo(repo)["status"] == "updated"

    inventory_path = repo / "sync" / "generated" / "upstream-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    assert inventory["head_sha"] == head
    assert inventory["changed_files"] == ["M\tREADME.md", "A\tadded.txt", "D\tremoved.txt"]
    assert len(inventory["recent_commits"]) == min(updates, 12)
    assert all("Initial checkpoint" not in commit for commit in inventory["recent_commits"])
    state_path = repo / "sync" / "upstream-state.json"
    assert json.loads(state_path.read_text())["last_synced_sha"] == head
    state_before = state_path.read_bytes()
    inventory_before = inventory_path.read_bytes()
    assert sync_repo(repo)["status"] == "noop"
    assert state_path.read_bytes() == state_before
    assert inventory_path.read_bytes() == inventory_before


@pytest.mark.parametrize("previous", ["0" * 40, "not-a-commit"])
def test_unavailable_checkpoint_preserves_state_and_generated_output(tmp_path: Path, previous: str) -> None:
    upstream, _, _ = make_upstream(tmp_path, 1)
    repo = make_consumer(tmp_path, upstream, previous)
    generated = repo / "sync" / "generated"
    generated.mkdir()
    inventory = generated / "upstream-inventory.json"
    inventory.write_text('{"previous": "inventory"}\n')
    state = repo / "sync" / "upstream-state.json"
    before_state, before_inventory = state.read_bytes(), inventory.read_bytes()

    with pytest.raises(subprocess.CalledProcessError):
        sync_repo(repo)

    assert state.read_bytes() == before_state
    assert inventory.read_bytes() == before_inventory
    assert list(generated.iterdir()) == [inventory]


@pytest.mark.parametrize("existing", ["absent", "empty", "partial", "all"])
def test_failed_verification_restores_generated_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: str
) -> None:
    upstream, previous, head = make_upstream(tmp_path, 1)
    repo = make_consumer(tmp_path, upstream, previous)
    generated = repo / "sync" / "generated"
    names = ["upstream-inventory.json", "upstream-commands.json", "upstream-sync-report.md"]
    if existing != "absent":
        generated.mkdir()
    if existing in {"partial", "all"}:
        for name in names[:1] if existing == "partial" else names:
            (generated / name).write_bytes(f"Confirmed {name}\r\n".encode())
        (generated / "local-note.txt").write_bytes(b"Keep unrelated files.\n")
    before_files = {path.name: path.read_bytes() for path in generated.glob("*")}
    state = repo / "sync" / "upstream-state.json"
    before_state = state.read_bytes()
    commits = []

    def fail_verification(root: Path) -> None:
        # Verification must inspect the proposed output before it is confirmed.
        assert json.loads((generated / names[0]).read_text())["head_sha"] == head
        assert all((generated / name).exists() for name in names)
        assert state.read_bytes() == before_state
        raise subprocess.CalledProcessError(1, ["python", "-m", "pytest"])

    monkeypatch.setattr("codex_ads.sync.run_verification", fail_verification)
    monkeypatch.setattr("codex_ads.sync._commit_and_push", lambda *args: commits.append(args))

    with pytest.raises(subprocess.CalledProcessError):
        sync_repo(repo, verify=True, commit=True, push=True)

    assert state.read_bytes() == before_state
    assert {path.name: path.read_bytes() for path in generated.glob("*")} == before_files
    assert generated.exists() == (existing != "absent")
    assert commits == []


def test_successful_verification_keeps_new_output_and_advances_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upstream, previous, head = make_upstream(tmp_path, 1)
    repo = make_consumer(tmp_path, upstream, previous)
    generated = repo / "sync" / "generated"
    generated.mkdir()
    inventory = generated / "upstream-inventory.json"
    inventory.write_text('{"previous": "confirmed"}\n')
    state = repo / "sync" / "upstream-state.json"
    before_state = state.read_bytes()
    verified = []

    def verify_output(root: Path) -> None:
        assert root == repo.resolve()
        assert json.loads(inventory.read_text())["head_sha"] == head
        assert json.loads((generated / "upstream-commands.json").read_text()) == ["audit"]
        assert head in (generated / "upstream-sync-report.md").read_text()
        assert state.read_bytes() == before_state
        verified.append(root)

    monkeypatch.setattr("codex_ads.sync.run_verification", verify_output)

    assert sync_repo(repo, verify=True)["status"] == "updated"

    assert verified == [repo.resolve()]
    assert json.loads(inventory.read_text())["head_sha"] == head
    assert json.loads(state.read_text())["last_synced_sha"] == head
