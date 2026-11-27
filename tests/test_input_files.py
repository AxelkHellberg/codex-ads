from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INPUT_COMMANDS = [
    "audit", "google", "meta", "youtube", "linkedin", "tiktok", "microsoft", "apple",
    "creative", "landing", "budget", "plan", "competitor", "math", "test",
]


def run_cli(command: str, output: Path, input_path: Path | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, "-m", "codex_ads.cli", command, "--output-dir", str(output)]
    if input_path is not None:
        args.extend(["--input", str(input_path)])
    return subprocess.run(
        args,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=20,
    )


def assert_usage_error(result: subprocess.CompletedProcess, output: Path) -> None:
    assert result.returncode == 2
    assert "--input" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""
    assert not output.exists()


@pytest.mark.parametrize("command", INPUT_COMMANDS)
def test_all_input_commands_reject_array_roots(tmp_path: Path, command: str) -> None:
    source = tmp_path / "input.json"
    source.write_text("[]")
    output = tmp_path / "output"

    result = run_cli(command, output, source)

    assert_usage_error(result, output)
    assert "JSON object" in result.stderr


@pytest.mark.parametrize("value", [None, False, True, 42, 2.5, "text", ""])
def test_input_rejects_scalar_roots(tmp_path: Path, value: object) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps(value))
    output = tmp_path / "output"

    result = run_cli("audit", output, source)

    assert_usage_error(result, output)
    assert "JSON object" in result.stderr


@pytest.mark.parametrize("contents", [b"{bad", b"", b"\xff"])
def test_input_reports_parse_and_encoding_errors(tmp_path: Path, contents: bytes) -> None:
    source = tmp_path / "input.json"
    source.write_bytes(contents)
    output = tmp_path / "output"

    result = run_cli("audit", output, source)

    assert_usage_error(result, output)


@pytest.mark.parametrize("is_directory", [False, True])
def test_input_reports_file_read_errors(tmp_path: Path, is_directory: bool) -> None:
    source = tmp_path / "input.json"
    if is_directory:
        source.mkdir()
    output = tmp_path / "output"

    result = run_cli("audit", output, source)

    assert_usage_error(result, output)
    assert str(source) in result.stderr


@pytest.mark.parametrize("command", ["audit", "google", "creative", "math", "test"])
@pytest.mark.parametrize("with_input", [False, True])
def test_empty_object_and_omitted_input_retain_defaults(
    tmp_path: Path, command: str, with_input: bool
) -> None:
    source = tmp_path / "input.json"
    source.write_text("{}")
    output = tmp_path / "output"

    result = run_cli(command, output, source if with_input else None)

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert result.stderr == ""
    if command == "audit":
        summary = json.loads((output / "ads-audit-summary.json").read_text())
        assert summary["platforms"] == []
    elif command == "google":
        summary = json.loads((output / "google-audit.json").read_text())
        assert all(item["status"] == "warning" for item in summary["findings"])
    elif command == "creative":
        assert "- Score: `60.0`" in (output / "ADS-CREATIVE-AUDIT.md").read_text()
    elif command == "math":
        assert "- cpa: `None`" in (output / "ADS-MATH.md").read_text()
    else:
        assert "- baseline_rate: `0.03`" in (output / "ADS-TEST-PLAN.md").read_text()
