from __future__ import annotations

import json
import sys

import pytest

from codex_ads.cli import _load_brief, main
from codex_ads.creative import build_campaign_brief, write_campaign_brief


def test_generated_brief_round_trip_uses_only_angles(tmp_path, monkeypatch):
    profile = {
        "brand_name": "Northstar",
        "description": "Positioning is not an angle",
        "tone_keywords": ["clear"],
        "headline_themes": ["Proof first", "A simpler workflow"],
        "color_palette": ["#000000", "#ffffff"],
    }
    path = write_campaign_brief(tmp_path, build_campaign_brief(profile))
    assert _load_brief(str(path))["angles"] == profile["headline_themes"]
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile))
    monkeypatch.setattr(sys, "argv", ["codex-ads", "generate", "--brand-profile", str(profile_path), "--brief", str(path), "--output-dir", str(tmp_path)])
    main()
    manifest = json.loads((tmp_path / "ad-assets" / "asset-manifest.json").read_text())
    assert all("angle Proof first." in asset["prompt"] for asset in manifest["assets"])


@pytest.mark.parametrize("text, expected", [
    ("- Legacy angle\n- Second angle\n", ["Legacy angle", "Second angle"]),
    ("## Angles\n\n- Chosen angle\n## Concepts\n- Unrelated hook\n", ["Chosen angle"]),
    ("## Angles\n\n## Concepts\n- Unrelated hook\n", ["performance clarity"]),
    ("## Concepts\n- Unrelated hook\n", ["performance clarity"]),
    ("# Brief\n\n## angles ##\n- Chosen angle\n", ["Chosen angle"]),
    ("## Angles\n-   \n", ["performance clarity"]),
])
def test_brief_angle_sections(tmp_path, text, expected):
    path = tmp_path / "brief.md"
    path.write_text(text)
    assert _load_brief(str(path))["angles"] == expected
