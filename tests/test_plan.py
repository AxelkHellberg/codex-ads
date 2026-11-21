from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from codex_ads.engine import build_generic_analysis


ROOT = Path(__file__).resolve().parents[1]
INVALID_TYPES = [None, True, False, 3, 1.5, [], {}, "", " \t\n"]


@pytest.mark.parametrize("business_type", INVALID_TYPES)
def test_plan_rejects_invalid_business_type(business_type: object) -> None:
    with pytest.raises(ValueError, match="business_type must be a nonblank string"):
        build_generic_analysis("plan", {"business_type": business_type})


@pytest.mark.parametrize(
    ("payload", "business_type", "first_phase"),
    [
        ({}, "saas", "Search + demand capture"),
        ({"business_type": "saas"}, "saas", "Search + demand capture"),
        ({"business_type": "ecommerce"}, "ecommerce", "Search + shopping"),
        ({"business_type": "local-service"}, "local-service", "Search + calls"),
        ({"business_type": "b2b-enterprise"}, "b2b-enterprise", "LinkedIn demand capture"),
        ({"business_type": "custom"}, "custom", "Intent capture"),
        ({"business_type": " custom "}, " custom ", "Intent capture"),
    ],
)
def test_plan_preserves_valid_business_type_and_phases(
    payload: dict, business_type: str, first_phase: str
) -> None:
    plan = build_generic_analysis("plan", payload)

    assert plan["title"] == f"Media Plan for {business_type}"
    assert plan["metrics"] == {"phases": 3, "business_type": business_type}
    assert plan["priorities"][0] == f"Phase 1: {first_phase}"
    assert plan["score"] == 88.0
    assert plan["status"] == "strong"


def run_plan(input_path: Path, output_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, "-m", "codex_ads.cli", "plan",
            "--input", str(input_path), "--output-dir", str(output_dir), *extra,
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True,
        capture_output=True,
        timeout=30,
    )


@pytest.mark.parametrize("business_type", INVALID_TYPES)
def test_plan_cli_rejects_invalid_business_type_before_output(
    tmp_path: Path, business_type: object
) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"business_type": business_type}))
    output_dir = tmp_path / "output"

    result = run_plan(input_path, output_dir)

    assert result.returncode == 2
    assert "business_type must be a nonblank string" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output_dir.exists()


@pytest.mark.parametrize("override", ["", " \t"])
def test_plan_cli_rejects_explicit_blank_override(tmp_path: Path, override: str) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"business_type": "saas"}))
    output_dir = tmp_path / "output"

    result = run_plan(input_path, output_dir, "--business-type", override)

    assert result.returncode == 2
    assert "business_type must be a nonblank string" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output_dir.exists()


def test_plan_cli_valid_override_replaces_invalid_payload(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"business_type": []}))
    output_dir = tmp_path / "output"

    result = run_plan(input_path, output_dir, "--business-type", "ecommerce")

    assert result.returncode == 0, result.stderr
    report = (output_dir / "ADS-PLAN.md").read_text()
    assert "# Media Plan for ecommerce" in report
    assert "Phase 1: Search + shopping" in report
