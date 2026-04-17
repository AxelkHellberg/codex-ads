from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_plugin_manifest_points_to_existing_assets_and_skills() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "codex-ads"
    assert (ROOT / manifest["skills"].replace("./", "")).exists()
    assert (ROOT / manifest["interface"]["composerIcon"].replace("./", "")).exists()
    assert (ROOT / manifest["interface"]["logo"].replace("./", "")).exists()


def test_expected_skill_surface_exists() -> None:
    skill_dirs = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
    assert "ads" in skill_dirs
    assert "ads-generate" in skill_dirs
    assert "ads-photoshoot" in skill_dirs
    assert len(skill_dirs) == 21
