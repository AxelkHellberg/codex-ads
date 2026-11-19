from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from codex_ads.creative import generate_asset_prompts, generate_photoshoot_set


ROOT = Path(__file__).resolve().parents[1]
PROFILE = {
    "brand_name": "Northstar",
    "tone_keywords": ["clear", "credible"],
    "color_palette": ["#112233", "#445566", "#778899"],
}
NS = "{http://www.w3.org/2000/svg}"


def generate(command: str, output: Path, profile: object) -> dict:
    if command == "generate":
        return generate_asset_prompts(output, profile, {"angles": ["proof"]})
    return generate_photoshoot_set(output, profile, "Northstar Box")


@pytest.mark.parametrize("command", ["generate", "photoshoot"])
@pytest.mark.parametrize("profile, field", [
    (None, "profile"),
    ([], "profile"),
    ({key: value for key, value in PROFILE.items() if key != "brand_name"}, "profile.brand_name"),
    ({**PROFILE, "brand_name": 123}, "profile.brand_name"),
    ({**PROFILE, "brand_name": " \t"}, "profile.brand_name"),
    ({**PROFILE, "tone_keywords": "clean"}, "profile.tone_keywords"),
    ({**PROFILE, "tone_keywords": ["clear", 123]}, "profile.tone_keywords"),
    ({**PROFILE, "tone_keywords": ["clear", " "]}, "profile.tone_keywords"),
    ({key: value for key, value in PROFILE.items() if key != "color_palette"}, "profile.color_palette"),
    ({**PROFILE, "color_palette": "#112233"}, "profile.color_palette"),
    ({**PROFILE, "color_palette": []}, "profile.color_palette"),
    ({**PROFILE, "color_palette": [None]}, "profile.color_palette"),
    ({**PROFILE, "color_palette": [" \t"]}, "profile.color_palette"),
])
def test_invalid_profile_fails_before_output(tmp_path: Path, command: str, profile: object, field: str) -> None:
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=rf"^{field.replace('.', '[.]')} must be"):
        generate(command, output, profile)
    assert not output.exists()


@pytest.mark.parametrize("command", ["generate", "photoshoot"])
@pytest.mark.parametrize("palette", [["#112233"], ["#112233", "#445566"], PROFILE["color_palette"]])
def test_valid_profile_preserves_text_palette_and_fallbacks(tmp_path: Path, command: str, palette: list[str]) -> None:
    profile = {**PROFILE, "brand_name": " Café Northstar ", "tone_keywords": ["clean", " café proof "], "color_palette": palette}
    result = generate(command, tmp_path, profile)
    manifest = json.loads(result["manifest"].read_text())
    records = manifest["assets"] if command == "generate" else manifest["styles"]
    assert len(records) == (4 if command == "generate" else 5)
    for record in records:
        assert " Café Northstar " in record["prompt"]
        assert "clean,  café proof " in record["prompt"]
    for path in result["asset_dir"].glob("*.svg"):
        root = ET.parse(path).getroot()
        assert [rect.attrib["fill"] for rect in root.findall(f"{NS}rect")] == [palette[0], palette[1] if len(palette) > 1 else "#1f2937"]
        assert root.find(f"{NS}text").attrib["fill"] == (palette[2] if len(palette) > 2 else "#f4f6f8")


def test_prompt_only_generation_does_not_require_unused_palette(tmp_path: Path) -> None:
    profile = {"brand_name": "Northstar", "tone_keywords": []}
    result = generate_asset_prompts(tmp_path, profile, {"angles": ["proof"]}, placeholder=False)
    manifest = json.loads(result["manifest"].read_text())
    assert len(manifest["assets"]) == 4
    assert not list(result["asset_dir"].glob("*.svg"))


@pytest.mark.parametrize("command", ["generate", "photoshoot"])
@pytest.mark.parametrize("field, value", [("tone_keywords", "clean"), ("color_palette", [])])
def test_cli_reports_profile_error_without_partial_assets(tmp_path: Path, command: str, field: str, value: object) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({**PROFILE, field: value}))
    args = ["--brand-profile", str(profile_path), "--output-dir", str(tmp_path / "output")]
    if command == "generate":
        brief_path = tmp_path / "brief.json"
        brief_path.write_text(json.dumps({"angles": ["proof"]}))
        args.extend(["--brief-json", str(brief_path)])
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", command, *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert f"profile.{field} must be" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "output").exists()
