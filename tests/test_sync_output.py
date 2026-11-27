from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from codex_ads import cli, sync


def _diagnostic_command(exit_code: int) -> list[str]:
    return [
        sys.executable,
        "-c",
        "import sys; print('child stdout', flush=True); "
        "print('child stderr', file=sys.stderr, flush=True); "
        f"sys.exit({exit_code})",
    ]


@pytest.mark.parametrize("exit_code", [0, 3])
def test_uncaptured_commands_send_all_diagnostics_to_stderr(capfd, exit_code: int) -> None:
    if exit_code:
        with pytest.raises(subprocess.CalledProcessError) as raised:
            sync._run(_diagnostic_command(exit_code), capture=False)
        assert raised.value.returncode == exit_code
    else:
        result = sync._run(_diagnostic_command(exit_code), capture=False)
        assert result.returncode == 0
    output = capfd.readouterr()
    assert output.out == ""
    assert "child stdout" in output.err
    assert "child stderr" in output.err


@pytest.mark.parametrize("exit_code", [0, 3])
def test_captured_commands_keep_separate_streams(capfd, exit_code: int) -> None:
    if exit_code:
        with pytest.raises(subprocess.CalledProcessError) as raised:
            sync._run(_diagnostic_command(exit_code))
        result = raised.value
    else:
        result = sync._run(_diagnostic_command(exit_code))
    assert result.stdout == "child stdout\n"
    assert result.stderr == "child stderr\n"
    output = capfd.readouterr()
    assert output.out == output.err == ""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


@pytest.fixture
def local_sync(tmp_path: Path, monkeypatch):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / ".claude-plugin").mkdir()
    (upstream / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"repository": "https://example.test/local-upstream", "version": "1"})
    )
    (upstream / "README.md").write_text("Use `/ads audit`.\n")
    _git(upstream, "init", "-b", "main")
    _git(upstream, "config", "user.name", "Test")
    _git(upstream, "config", "user.email", "test@example.test")
    _git(upstream, "add", ".")
    _git(upstream, "-c", "commit.gpgsign=false", "commit", "-m", "Initial fixture")
    head = _git(upstream, "rev-parse", "HEAD")

    repo = tmp_path / "consumer"
    (repo / "sync").mkdir(parents=True)
    (repo / "sync" / "upstream-map.yaml").write_text(json.dumps({"rules": []}))
    state_path = repo / "sync" / "upstream-state.json"
    state_path.write_text(
        json.dumps({"upstream_repo": str(upstream), "tracked_branch": "main", "last_synced_sha": None})
    )
    (repo / "test_verification.py").write_text("def test_local_verification():\n    assert True\n")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["codex-ads", "sync", "--verify"])
    return repo, state_path, head


def test_verified_sync_cli_stdout_is_one_json_document(local_sync, capfd) -> None:
    repo, state_path, head = local_sync
    cli.main()
    output = capfd.readouterr()
    result = json.loads(output.out)
    assert result["status"] == "updated"
    assert result["head_sha"] == head
    assert "1 passed" in output.err
    assert json.loads(state_path.read_text())["last_synced_sha"] == head
    assert (repo / "sync" / "generated" / "upstream-inventory.json").exists()


def test_failed_verification_keeps_stdout_empty_and_checkpoint_unchanged(local_sync, capfd) -> None:
    repo, state_path, _ = local_sync
    (repo / "test_verification.py").write_text("def test_local_verification():\n    assert False\n")
    original_state = state_path.read_bytes()
    with pytest.raises(subprocess.CalledProcessError) as raised:
        cli.main()
    assert raised.value.returncode == 1
    output = capfd.readouterr()
    assert output.out == ""
    assert "1 failed" in output.err
    assert state_path.read_bytes() == original_state


def test_sync_noop_cli_stdout_remains_one_json_document(local_sync, capfd) -> None:
    _, state_path, head = local_sync
    state = json.loads(state_path.read_text())
    state["last_synced_sha"] = head
    state_path.write_text(json.dumps(state))
    cli.main()
    output = capfd.readouterr()
    assert json.loads(output.out) == {
        "status": "noop", "head_sha": head, "message": "Upstream unchanged."
    }
    assert output.err == ""
