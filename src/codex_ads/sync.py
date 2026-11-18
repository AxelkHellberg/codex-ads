from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


UPSTREAM_REPO = "https://github.com/AgriciDaniel/claude-ads.git"
DEFAULT_BRANCH = "main"
GENERATED_FILENAMES = (
    "upstream-inventory.json",
    "upstream-sync-report.md",
    "upstream-commands.json",
)
SYNC_PATHS = tuple(f"sync/generated/{name}" for name in GENERATED_FILENAMES) + ("sync/upstream-state.json",)


def _run(cmd: list[str], cwd: str | Path | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
        text=True,
        capture_output=capture,
    )


def load_mapping(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def load_state(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def save_state(path: str | Path, state: dict) -> None:
    Path(path).write_text(json.dumps(state, indent=2) + "\n")


def upstream_head(repo: str = UPSTREAM_REPO, branch: str = DEFAULT_BRANCH) -> str:
    result = _run(["git", "ls-remote", repo, f"refs/heads/{branch}"])
    return result.stdout.split()[0]


def _skill_inventory(root: Path) -> list[dict]:
    items = []
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        text = skill.read_text()
        description_match = re.search(r'description:\s*"?(.*?)"?$', text, re.M)
        items.append(
            {
                "directory": skill.parent.name,
                "description": description_match.group(1) if description_match else "",
            }
        )
    return items


def _readme_commands(root: Path) -> list[str]:
    readme = (root / "README.md").read_text()
    return sorted(set(re.findall(r"`/ads ([^`]+)`", readme)))


def _agent_inventory(root: Path) -> list[str]:
    return sorted(path.name for path in (root / "agents").glob("*.md"))


def _script_inventory(root: Path) -> list[str]:
    return sorted(path.name for path in (root / "scripts").glob("*.py"))


def collect_upstream_snapshot(root: Path, previous_sha: str | None, current_sha: str) -> dict:
    plugin_json = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
    commits = _run(
        ["git", "log", "--oneline", "--max-count", "12", current_sha if previous_sha is None else f"{previous_sha}..{current_sha}"],
        cwd=root,
    ).stdout.splitlines()

    if previous_sha:
        diff = _run(["git", "diff", "--name-status", previous_sha, current_sha], cwd=root).stdout.splitlines()
    else:
        diff = ["A\t" + str(path.relative_to(root)) for path in sorted(root.glob("**/*")) if path.is_file() and ".git/" not in str(path)]

    return {
        "upstream_repo": plugin_json.get("repository", UPSTREAM_REPO.removesuffix(".git")),
        "upstream_version": plugin_json.get("version"),
        "head_sha": current_sha,
        "commands": _readme_commands(root),
        "skills": _skill_inventory(root),
        "agents": _agent_inventory(root),
        "scripts": _script_inventory(root),
        "changed_files": diff,
        "recent_commits": commits,
    }


def write_generated(repo_root: Path, snapshot: dict) -> dict[str, Path]:
    generated = repo_root / "sync" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    inventory_path, report_path, commands_path = (generated / name for name in GENERATED_FILENAMES)

    inventory_path.write_text(json.dumps(snapshot, indent=2) + "\n")
    commands_path.write_text(json.dumps(snapshot["commands"], indent=2) + "\n")

    lines = [
        "# Upstream Sync Report",
        "",
        f"- Upstream repo: `{snapshot['upstream_repo']}`",
        f"- Head SHA: `{snapshot['head_sha']}`",
        f"- Version: `{snapshot['upstream_version']}`",
        "",
        "## Recent commits",
        "",
    ]
    if snapshot["recent_commits"]:
        lines.extend(f"- `{commit}`" for commit in snapshot["recent_commits"])
    else:
        lines.append("- No commit window available.")
    lines.extend(["", "## Changed files", ""])
    lines.extend(f"- `{item}`" for item in snapshot["changed_files"][:120])
    lines.extend(["", "## Command inventory", ""])
    lines.extend(f"- `{command}`" for command in snapshot["commands"])
    report_path.write_text("\n".join(lines).strip() + "\n")
    return {"inventory": inventory_path, "commands": commands_path, "report": report_path}


def run_verification(repo_root: Path) -> None:
    _run([sys.executable, "-m", "pytest"], cwd=repo_root, capture=False)


def _write_verified_generated(repo_root: Path, snapshot: dict) -> None:
    generated = repo_root / "sync" / "generated"
    directory_existed = generated.exists()
    previous = {
        generated / name: (generated / name).read_bytes() if (generated / name).exists() else None
        for name in GENERATED_FILENAMES
    }
    try:
        write_generated(repo_root, snapshot)
        run_verification(repo_root)
    except BaseException:
        # Keep the last confirmed inventory paired with its unchanged checkpoint.
        for path, content in previous.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        if not directory_existed and generated.exists() and not any(generated.iterdir()):
            generated.rmdir()
        raise


def _git_changed(repo_root: Path) -> bool:
    result = _run(["git", "status", "--porcelain", "--", *SYNC_PATHS], cwd=repo_root)
    return bool(result.stdout.strip())


def _commit_and_push(repo_root: Path, message: str, push: bool) -> None:
    if not _git_changed(repo_root):
        return
    _run(["git", "add", "--", *SYNC_PATHS], cwd=repo_root)
    # A normal commit would also consume any unrelated work already in the index.
    _run(["git", "commit", "--only", "-m", message, "--", *SYNC_PATHS], cwd=repo_root)
    if push:
        _run(["git", "push", "origin", "HEAD:main"], cwd=repo_root, capture=False)


def sync_repo(
    repo_root: str | Path,
    verify: bool = False,
    commit: bool = False,
    push: bool = False,
) -> dict:
    root = Path(repo_root).resolve()
    mapping = load_mapping(root / "sync" / "upstream-map.yaml")
    state_path = root / "sync" / "upstream-state.json"
    state = load_state(state_path)
    source_repo = state.get("upstream_repo", UPSTREAM_REPO)
    tracked_branch = state.get("tracked_branch", DEFAULT_BRANCH)
    head = upstream_head(source_repo, tracked_branch)

    if head == state.get("last_synced_sha"):
        return {"status": "noop", "head_sha": head, "message": "Upstream unchanged."}

    with tempfile.TemporaryDirectory(prefix="codex-ads-sync-") as tmp_dir:
        checkout = Path(tmp_dir) / "upstream"
        _run(["git", "clone", "--depth", "50", "--branch", tracked_branch,
              "--single-branch", source_repo, str(checkout)], capture=False)
        _run(["git", "checkout", head], cwd=checkout)
        previous_sha = state.get("last_synced_sha")
        if previous_sha:
            try:
                _run(["git", "cat-file", "-e", f"{previous_sha}^{{commit}}"], cwd=checkout)
            except subprocess.CalledProcessError:
                # A missed sync can put the checkpoint outside the shallow clone.
                _run(["git", "fetch", "--depth", "1", "origin", previous_sha], cwd=checkout)
                _run(["git", "cat-file", "-e", f"{previous_sha}^{{commit}}"], cwd=checkout)
        snapshot = collect_upstream_snapshot(checkout, previous_sha, head)
        snapshot["mapping_rules"] = mapping["rules"]
        if verify:
            _write_verified_generated(root, snapshot)
        else:
            write_generated(root, snapshot)

    state.update(
        {
            "last_checked_sha": head,
            "last_synced_sha": head,
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "last_result": "success",
        }
    )
    save_state(state_path, state)

    message = f"sync: port upstream changes from claude-ads {head[:7]}"
    if commit:
        _commit_and_push(root, message, push)

    return {"status": "updated", "head_sha": head, "message": message}
