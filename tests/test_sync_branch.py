from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from codex_ads.sync import sync_repo


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.mark.parametrize("tracked_branch", ["release/content", "main"])
def test_sync_fetches_configured_branch(tmp_path, tracked_branch):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "Test")
    git(upstream, "config", "user.email", "test@example.com")
    (upstream / ".claude-plugin").mkdir()
    (upstream / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": "main"}))
    (upstream / "README.md").write_text("Use `/ads main`.\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "Default branch")
    git(upstream, "checkout", "-b", "release/content")
    (upstream / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": "release"}))
    (upstream / "README.md").write_text("Use `/ads release`.\n")
    git(upstream, "commit", "-am", "Release-only content")
    head = git(upstream, "rev-parse", tracked_branch)
    git(upstream, "checkout", "main")

    repo = tmp_path / "consumer"
    (repo / "sync").mkdir(parents=True)
    (repo / "sync" / "upstream-map.yaml").write_text('{"rules": []}')
    state_path = repo / "sync" / "upstream-state.json"
    state_path.write_text(json.dumps({"upstream_repo": upstream.as_uri(), "tracked_branch": tracked_branch, "last_synced_sha": None}))
    result = sync_repo(repo)
    assert result["head_sha"] == head
    inventory = json.loads((repo / "sync" / "generated" / "upstream-inventory.json").read_text())
    assert inventory["commands"] == ["release" if tracked_branch != "main" else "main"]
    assert inventory["upstream_version"] == ("release" if tracked_branch != "main" else "main")
    assert json.loads(state_path.read_text())["last_synced_sha"] == head
    assert sync_repo(repo)["status"] == "noop"
