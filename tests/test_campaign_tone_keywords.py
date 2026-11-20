from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.creative import BrandProfileError, build_campaign_brief, write_campaign_brief


ROOT = Path(__file__).resolve().parents[1]
PROFILE = {"brand_name": "Northstar"}
ERROR = "profile.tone_keywords must be a list of nonempty strings"


@pytest.mark.parametrize("tone", [
    "clear", "", None, 5, False, {"clear": True},
    ["clear", 5], [None], [""], [" \t\n"],
    ["clear", "credible", "simple", None],
])
def test_campaign_rejects_invalid_tone_keywords(tone) -> None:
    with pytest.raises(BrandProfileError, match=r"^profile[.]tone_keywords must be"):
        build_campaign_brief({**PROFILE, "tone_keywords": tone})


@pytest.mark.parametrize("profile", [PROFILE, {**PROFILE, "tone_keywords": []}])
def test_campaign_keeps_missing_or_empty_tone_default(profile, tmp_path: Path) -> None:
    brief = build_campaign_brief(profile)
    assert brief["tone_keywords"] == []
    assert brief["concepts"][0]["hook"] == "Northstar delivers  outcomes without wasting budget."
    assert "- Tone: \n" in write_campaign_brief(tmp_path, brief).read_text()


def test_campaign_preserves_tone_text_and_order(tmp_path: Path) -> None:
    tones = [" clear ", "crédible", "simple", "fourth"]
    brief = build_campaign_brief({**PROFILE, "tone_keywords": tones})
    assert brief["tone_keywords"] == tones
    assert brief["concepts"][0]["hook"] == "Northstar delivers  clear , crédible, simple outcomes without wasting budget."
    assert "- Tone:  clear , crédible, simple, fourth\n" in write_campaign_brief(tmp_path, brief).read_text()


def run_create(tmp_path: Path, profile: dict) -> subprocess.CompletedProcess[str]:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile))
    return subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "create", "--brand-profile", str(profile_path),
         "--output-dir", str(tmp_path / "output")],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("tone", ["clear", None, ["clear", 5], ["clear", " "]])
def test_create_cli_rejects_invalid_tones_before_output(tmp_path: Path, tone) -> None:
    result = run_create(tmp_path, {**PROFILE, "tone_keywords": tone})
    assert result.returncode == 2
    assert ERROR in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("profile", [
    PROFILE,
    {**PROFILE, "tone_keywords": []},
    {**PROFILE, "tone_keywords": ["clear", "crédible"]},
])
def test_create_cli_keeps_valid_tones_and_defaults(tmp_path: Path, profile: dict) -> None:
    result = run_create(tmp_path, profile)
    assert result.returncode == 0, result.stderr
    text = (tmp_path / "output" / "campaign-brief.md").read_text()
    assert f"- Tone: {', '.join(profile.get('tone_keywords', []))}\n" in text
