from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.creative import build_campaign_brief


ROOT = Path(__file__).resolve().parents[1]
PROFILE = {"brand_name": "Example", "tone_keywords": ["clear"]}
DEFAULT_PHASES = ["acquisition", "retargeting", "expansion"]


@pytest.mark.parametrize("context", [None, {}, {"phases": None}, {"phases": []}])
def test_default_phases_remain_available(context) -> None:
    brief = build_campaign_brief(PROFILE, context)
    assert [concept["phase"] for concept in brief["concepts"]] == DEFAULT_PHASES


def test_valid_phases_retain_order_and_text() -> None:
    phases = ["proof", "  Rétention  "]
    brief = build_campaign_brief(PROFILE, {"phases": phases})
    assert [concept["phase"] for concept in brief["concepts"]] == phases
    assert [concept["headline"] for concept in brief["concepts"]] == [
        "Example for proof", "Example for   Rétention  "
    ]
    assert brief["angles"] == ["proof", "clarity", "speed"]


INVALID_PHASES = ["retargeting", "", {"proof": True}, 2, 0, True, False,
                  ["proof", 4], [None], [True], [""], [" \t\n"], [["proof"]]]


@pytest.mark.parametrize("phases", INVALID_PHASES)
def test_invalid_phases_are_rejected_before_concept_generation(phases) -> None:
    with pytest.raises(ValueError, match="context.phases must be a list of nonblank strings"):
        build_campaign_brief(PROFILE, {"phases": phases})


@pytest.mark.parametrize("phases", ["retargeting", ["proof", 4], [" \t"]])
def test_create_cli_rejects_invalid_phases_without_writing_brief(tmp_path: Path, phases) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(PROFILE))
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps({"phases": phases}))
    output_dir = tmp_path / "output"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "create", "--brand-profile", str(profile_path),
         "--context", str(context_path), "--output-dir", str(output_dir)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert "context.phases must be a list of nonblank strings" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output_dir.exists()


def test_create_cli_writes_one_concept_per_valid_phase(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(PROFILE))
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps({"phases": ["proof", "loyalty"]}))
    output_dir = tmp_path / "output"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "create", "--brand-profile", str(profile_path),
         "--context", str(context_path), "--output-dir", str(output_dir)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    brief = (output_dir / "campaign-brief.md").read_text()
    assert "### Proof\n" in brief
    assert "### Loyalty\n" in brief
    assert brief.count("\n### ") == 2
