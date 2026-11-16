from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.creative import generate_asset_prompts


ROOT = Path(__file__).resolve().parents[1]
PROFILE = {
    "brand_name": "Example",
    "tone_keywords": ["clear"],
    "color_palette": ["#ffffff", "#000000", "#eeeeee"],
}


@pytest.mark.parametrize("brief", [None, [], "proof", 1])
def test_generation_requires_brief_object(tmp_path: Path, brief: object) -> None:
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="brief must be a JSON object"):
        generate_asset_prompts(output, PROFILE, brief)
    assert not output.exists()


@pytest.mark.parametrize(
    "brief",
    [
        {},
        {"angles": None},
        {"angles": []},
        {"angles": "proof"},
        {"angles": {"0": "proof"}},
        {"angles": [123]},
        {"angles": [False]},
        {"angles": [None]},
        {"angles": [""]},
        {"angles": [" \t\n"]},
        {"angles": ["proof", 123]},
    ],
)
def test_invalid_angles_fail_before_output(tmp_path: Path, brief: dict) -> None:
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=r"brief\.angles must be a nonempty list of nonempty strings"):
        generate_asset_prompts(output, PROFILE, brief)
    assert not output.exists()


@pytest.mark.parametrize("placeholder", [True, False])
def test_valid_angle_is_preserved_in_every_prompt(tmp_path: Path, placeholder: bool) -> None:
    angle = "Proof with café & customer results"
    result = generate_asset_prompts(
        tmp_path, PROFILE, {"angles": [angle, "another angle"]}, placeholder=placeholder
    )
    manifest = json.loads(result["manifest"].read_text())
    assert len(manifest["assets"]) == 4
    for asset in manifest["assets"]:
        assert asset["prompt"].endswith(f"angle {angle}.")
        assert ("placeholder_path" in asset) is placeholder
    assert result["prompts"].read_text().count(f"angle {angle}.") == 4
    assert len(list(result["asset_dir"].glob("*.svg"))) == (4 if placeholder else 0)


def run_generate(tmp_path: Path, brief: object) -> subprocess.CompletedProcess:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(PROFILE))
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(brief))
    return subprocess.run(
        [
            sys.executable, "-m", "codex_ads.cli", "generate",
            "--brand-profile", str(profile_path), "--brief-json", str(brief_path),
            "--output-dir", str(tmp_path / "output"),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("brief", [{"angles": "proof"}, {"angles": []}, []])
def test_cli_rejects_malformed_json_brief_without_assets(tmp_path: Path, brief: object) -> None:
    result = run_generate(tmp_path, brief)
    assert result.returncode != 0
    assert "ValueError: brief" in result.stderr
    assert not (tmp_path / "output").exists()


def test_cli_generates_assets_from_valid_json_brief(tmp_path: Path) -> None:
    result = run_generate(tmp_path, {"angles": ["full customer proof", "clarity"]})
    assert result.returncode == 0, result.stderr
    paths = json.loads(result.stdout)
    manifest = json.loads(Path(paths["manifest"]).read_text())
    assert len(manifest["assets"]) == 4
    assert all(asset["prompt"].endswith("angle full customer proof.") for asset in manifest["assets"])
