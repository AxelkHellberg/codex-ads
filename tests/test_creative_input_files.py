from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
JSON_OPTIONS = [
    ("create", "--brand-profile"),
    ("generate", "--brand-profile"),
    ("photoshoot", "--brand-profile"),
    ("create", "--context"),
    ("generate", "--brief-json"),
]
PROFILE = {
    "brand_name": "Example",
    "tone_keywords": ["clear"],
    "color_palette": ["#102030", "#405060", "#f4f6f8"],
}


def run_cli(
    directory: Path, command: str, output: Path, *options: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, "-m", "codex_ads.cli", command,
            "--output-dir", str(output), *options,
        ],
        cwd=directory,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=20,
    )


def setup_inputs(directory: Path) -> None:
    (directory / "brand-profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
    (directory / "campaign-brief.md").write_text("## Angles\n\n- clarity\n", encoding="utf-8")


@pytest.mark.parametrize("command,option", JSON_OPTIONS)
@pytest.mark.parametrize(
    "contents",
    [b"{bad", b"", b"\xff", b"[]", b"null", b"false", b"42", b'"text"'],
    ids=["malformed", "empty", "encoding", "array", "null", "boolean", "number", "string"],
)
def test_creative_json_options_reject_invalid_files_before_output(
    tmp_path: Path, command: str, option: str, contents: bytes
) -> None:
    setup_inputs(tmp_path)
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(contents)
    output = tmp_path / "output"

    result = run_cli(tmp_path, command, output, option, str(invalid))

    assert result.returncode == 2, result.stderr
    assert option in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
    assert not output.exists()


@pytest.mark.parametrize("command,option", JSON_OPTIONS)
@pytest.mark.parametrize("is_directory", [False, True], ids=["missing", "directory"])
def test_creative_json_options_report_file_errors_before_output(
    tmp_path: Path, command: str, option: str, is_directory: bool
) -> None:
    setup_inputs(tmp_path)
    invalid = tmp_path / "invalid.json"
    if is_directory:
        invalid.mkdir()
    output = tmp_path / "output"

    result = run_cli(tmp_path, command, output, option, str(invalid))

    assert result.returncode == 2, result.stderr
    assert option in result.stderr
    assert str(invalid) in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
    assert not output.exists()


@pytest.mark.parametrize("command", ["create", "generate", "photoshoot"])
@pytest.mark.parametrize("explicit_options", [False, True], ids=["defaults", "explicit"])
def test_creative_commands_preserve_valid_files_and_optional_defaults(
    tmp_path: Path, command: str, explicit_options: bool
) -> None:
    setup_inputs(tmp_path)
    output = tmp_path / "output"
    options = []
    if explicit_options:
        options.extend(["--brand-profile", str(tmp_path / "brand-profile.json")])
        if command == "create":
            context = tmp_path / "context.json"
            context.write_text('{"phases": ["retention"]}', encoding="utf-8")
            options.extend(["--context", str(context)])
        elif command == "generate":
            brief = tmp_path / "brief.json"
            brief.write_text('{"angles": ["proof"]}', encoding="utf-8")
            options.extend(["--brief-json", str(brief)])

    result = run_cli(tmp_path, command, output, *options)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    if command == "create":
        text = (output / "campaign-brief.md").read_text(encoding="utf-8")
        assert "Example" in text
        expected_heading = "### Retention" if explicit_options else "### Acquisition"
        assert expected_heading in text
    elif command == "generate":
        manifest = json.loads((output / "ad-assets" / "asset-manifest.json").read_text(encoding="utf-8"))
        assert manifest["brand"] == "Example"
        assert len(manifest["assets"]) == 4
        angle = "proof" if explicit_options else "clarity"
        assert all(f"angle {angle}." in asset["prompt"] for asset in manifest["assets"])
    else:
        manifest = json.loads((output / "ad-assets" / "photoshoot-prompts.json").read_text(encoding="utf-8"))
        assert manifest["product_name"] == "Product"
        assert len(manifest["styles"]) == 5


def test_empty_context_object_retains_campaign_defaults(tmp_path: Path) -> None:
    setup_inputs(tmp_path)
    context = tmp_path / "context.json"
    context.write_text("{}", encoding="utf-8")
    output = tmp_path / "output"

    result = run_cli(tmp_path, "create", output, "--context", str(context))

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    text = (output / "campaign-brief.md").read_text(encoding="utf-8")
    assert "### Acquisition" in text
    assert "### Retargeting" in text
    assert "### Expansion" in text
