from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from codex_ads import sync as sync_module


def _git(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def test_sync_repo_generates_inventory_from_local_upstream(tmp_path: Path, monkeypatch) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / ".claude-plugin").mkdir()
    (upstream / "ads").mkdir()
    (upstream / "skills" / "ads-google").mkdir(parents=True)
    (upstream / "agents").mkdir()
    (upstream / "scripts").mkdir()
    (upstream / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"repository": "https://example.com/upstream", "version": "1.0.0"}) + "\n"
    )
    (upstream / "README.md").write_text("Use `/ads audit` and `/ads google`.\n")
    (upstream / "ads" / "SKILL.md").write_text("---\nname: ads\n---\n")
    (upstream / "skills" / "ads-google" / "SKILL.md").write_text('---\ndescription: "Google review"\n---\n')
    (upstream / "agents" / "audit-google.md").write_text("agent\n")
    (upstream / "scripts" / "generate_report.py").write_text("print('ok')\n")
    _git(["git", "init", "-b", "main"], upstream)
    _git(["git", "config", "user.name", "Test"], upstream)
    _git(["git", "config", "user.email", "test@example.com"], upstream)
    _git(["git", "add", "."], upstream)
    _git(["git", "commit", "-m", "init"], upstream)
    head = _git(["git", "rev-parse", "HEAD"], upstream)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "sync" / "generated").mkdir(parents=True)
    (repo / "sync" / "upstream-map.yaml").write_text((Path(__file__).resolve().parents[1] / "sync" / "upstream-map.yaml").read_text())
    (repo / "sync" / "upstream-state.json").write_text(
        json.dumps(
            {
                "upstream_repo": str(upstream),
                "tracked_branch": "main",
                "last_checked_sha": None,
                "last_synced_sha": None,
                "last_run_at": None,
                "last_result": "never",
            },
            indent=2,
        )
        + "\n"
    )

    monkeypatch.setattr(sync_module, "UPSTREAM_REPO", str(upstream))
    monkeypatch.setattr(sync_module, "upstream_head", lambda repo, branch: head)
    monkeypatch.setattr(sync_module, "run_verification", lambda repo_root: None)

    result = sync_module.sync_repo(repo, verify=True, commit=False, push=False)
    assert result["status"] == "updated"
    inventory = json.loads((repo / "sync" / "generated" / "upstream-inventory.json").read_text())
    assert inventory["head_sha"] == head
    assert "audit-google.md" in inventory["agents"]
