from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.creative import build_campaign_brief, write_campaign_brief


ROOT = Path(__file__).resolve().parents[1]
PROFILE = {"brand_name": "Example", "tone_keywords": ["clear"]}
ERROR = "profile.headline_themes must be a list of nonblank strings"


@pytest.mark.parametrize("themes", [
    "Proof that works", "", None, 5, False, {"proof": True},
    ["proof", 5], [None], [""], [" \t\n"],
    ["one", "two", "three", "four", None],
])
def test_invalid_headline_themes_are_rejected(themes) -> None:
    with pytest.raises(ValueError, match=r"^profile[.]headline_themes must be"):
        build_campaign_brief({**PROFILE, "headline_themes": themes})


@pytest.mark.parametrize("profile", [PROFILE, {**PROFILE, "headline_themes": []}])
def test_missing_or_empty_themes_retain_default_angles(profile) -> None:
    assert build_campaign_brief(profile)["angles"] == ["proof", "clarity", "speed"]


def test_valid_themes_keep_first_four_in_order_without_changing_text(tmp_path: Path) -> None:
    themes = ["Proof that works", "  Clarté  ", "speed", "trust", "fifth angle"]
    brief = build_campaign_brief({**PROFILE, "headline_themes": themes})
    assert brief["angles"] == themes[:4]
    target = write_campaign_brief(tmp_path, brief)
    angles = target.read_text().split("## Angles\n\n", 1)[1].split("\n\n## Concepts", 1)[0]
    assert angles == "\n".join(f"- {theme}" for theme in themes[:4])


@pytest.mark.parametrize("themes", ["Proof that works", None, ["proof", 5]])
def test_create_cli_reports_invalid_themes_before_writing_output(tmp_path: Path, themes) -> None:
    profile = tmp_path / "brand-profile.json"
    profile.write_text(json.dumps({**PROFILE, "headline_themes": themes}))
    output = tmp_path / "output"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "create", "--brand-profile", str(profile),
         "--output-dir", str(output)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert ERROR in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_create_cli_writes_complete_angle_bullets(tmp_path: Path) -> None:
    profile = tmp_path / "brand-profile.json"
    themes = ["Proof that works", "Customer stories"]
    profile.write_text(json.dumps({**PROFILE, "headline_themes": themes}))
    output = tmp_path / "output"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "create", "--brand-profile", str(profile),
         "--output-dir", str(output)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    text = (output / "campaign-brief.md").read_text()
    assert "## Angles\n\n- Proof that works\n- Customer stories\n" in text
