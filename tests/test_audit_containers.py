from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.engine import audit_platform, build_portfolio_audit


ROOT = Path(__file__).resolve().parents[1]
INVALID_OBJECTS = [None, [], "invalid", 7, False]


@pytest.mark.parametrize("value", INVALID_OBJECTS)
@pytest.mark.parametrize("location", ["input", "platforms", "platform", "metrics"])
def test_portfolio_rejects_malformed_consumed_containers(value, location):
    payload = {
        "input": value,
        "platforms": {"platforms": value},
        "platform": {"platforms": {"google": value}},
        "metrics": {"platforms": {"google": {"metrics": value}}},
    }[location]
    field = {
        "input": "audit input",
        "platforms": "platforms",
        "platform": "platforms.google",
        "metrics": "google.metrics",
    }[location]
    with pytest.raises(ValueError, match=rf"{field} must be a JSON object"):
        build_portfolio_audit(payload)


@pytest.mark.parametrize("value", INVALID_OBJECTS)
@pytest.mark.parametrize("location", ["platform", "metrics"])
def test_platform_api_rejects_malformed_containers(value, location):
    payload = value if location == "platform" else {"metrics": value}
    field = "google" if location == "platform" else "google.metrics"
    with pytest.raises(ValueError, match=rf"{field} must be a JSON object"):
        audit_platform("google", payload)


@pytest.mark.parametrize("command", ["audit", "google"])
@pytest.mark.parametrize(
    "payload,field",
    [
        ([], "audit input"),
        ({"platforms": None}, "platforms"),
        ({"platforms": []}, "platforms"),
        ({"platforms": {"google": []}}, "google"),
        ({"platforms": {"google": {"metrics": "invalid"}}}, "google.metrics"),
    ],
)
def test_audit_cli_reports_container_errors_before_writing(tmp_path, command, payload, field):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload))
    output = tmp_path / "reports"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", command, "--input", str(source), "--output-dir", str(output)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert f"{field} must be a JSON object" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_platform_cli_validates_direct_metrics_container(tmp_path):
    source = tmp_path / "input.json"
    source.write_text('{"metrics": []}')
    output = tmp_path / "reports"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "meta", "--input", str(source), "--output-dir", str(output)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "meta.metrics must be a JSON object" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_valid_and_omitted_containers_keep_existing_results():
    assert audit_platform("google", {}) == audit_platform("google", {"metrics": {}})
    assert build_portfolio_audit({}) == build_portfolio_audit({"platforms": {}})
    platform = {"budget": 100, "metrics": {"conversion_tracking_enabled": True, "wasted_spend_pct": 0.08}}
    original = json.loads(json.dumps(platform))
    summary = build_portfolio_audit({"platforms": {"google": platform, "unrecognized": None}})
    result = summary["platforms"][0]
    expected = audit_platform("google", original)
    assert result == {**expected, "budget_share": 1.0}
    assert summary["score"] == expected["score"]
    assert platform == original


def test_portfolio_rejects_platform_arrays_that_dict_would_coerce():
    payload = {"platforms": {"google": [["metrics", {"conversion_tracking_enabled": True}]]}}
    with pytest.raises(ValueError, match="platforms.google must be a JSON object"):
        build_portfolio_audit(payload)


@pytest.mark.parametrize("shape", ["direct", "wrapped", "omitted"])
def test_platform_cli_keeps_valid_input_forms(tmp_path, shape):
    platform = {"metrics": {"conversion_tracking_enabled": True, "wasted_spend_pct": 0.08}}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(platform if shape == "direct" else {"platforms": {"google": platform}}))
    output = tmp_path / "reports"
    command = [sys.executable, "-m", "codex_ads.cli", "google", "--output-dir", str(output)]
    if shape != "omitted":
        command.extend(["--input", str(source)])
    result = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((output / "google-audit.json").read_text()) == audit_platform(
        "google", {} if shape == "omitted" else platform
    )
