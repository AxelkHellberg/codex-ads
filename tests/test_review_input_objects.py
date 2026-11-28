from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.engine import build_generic_analysis


ROOT = Path(__file__).resolve().parents[1]
INVALID_OBJECTS = [None, False, 0, "invalid", [], [["fatigue_index", 0.2]]]


@pytest.mark.parametrize("kind", ["creative", "landing"])
@pytest.mark.parametrize("value", INVALID_OBJECTS)
def test_review_input_must_be_an_object(kind, value):
    with pytest.raises(ValueError, match="Review input must be a JSON object"):
        build_generic_analysis(kind, value)


@pytest.mark.parametrize("kind", ["creative", "landing"])
@pytest.mark.parametrize("value", INVALID_OBJECTS)
def test_review_metrics_must_be_an_object(kind, value):
    with pytest.raises(ValueError, match="metrics must be a JSON object"):
        build_generic_analysis(kind, {"metrics": value})


def run_review(kind, source, output):
    return subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", kind, "--input", str(source),
         "--output-dir", str(output)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True,
        capture_output=True,
        timeout=30,
    )


@pytest.mark.parametrize("kind", ["creative", "landing"])
@pytest.mark.parametrize("value", INVALID_OBJECTS)
@pytest.mark.parametrize("container", ["input", "metrics"])
def test_cli_rejects_invalid_objects_without_creating_output(tmp_path, kind, value, container):
    payload = value if container == "input" else {"metrics": value}
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "reports"

    result = run_review(kind, source, output)

    assert result.returncode == 2
    expected = "Review input" if container == "input" else "metrics"
    assert f"{expected} must be a JSON object" in result.stderr
    assert "Traceback" not in result.stderr
    assert not result.stdout
    assert not output.exists()


@pytest.mark.parametrize("kind, filename, expected_score", [
    ("creative", "ADS-CREATIVE-AUDIT.md", 60.0),
    ("landing", "ADS-LANDING-AUDIT.md", 57.0),
])
@pytest.mark.parametrize("payload", [{}, {"metrics": {}}])
def test_cli_preserves_default_reviews(tmp_path, kind, filename, expected_score, payload):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "reports"

    result = run_review(kind, source, output)

    assert result.returncode == 0, result.stderr
    assert f"- Score: `{expected_score}`" in (output / filename).read_text(encoding="utf-8")
    assert not result.stderr


@pytest.mark.parametrize("kind, filename, metric", [
    ("creative", "ADS-CREATIVE-AUDIT.md", "fatigue_index"),
    ("landing", "ADS-LANDING-AUDIT.md", "message_match_score"),
])
def test_cli_metric_error_leaves_existing_report_unchanged(tmp_path, kind, filename, metric):
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"metrics": {metric: 2}}), encoding="utf-8")
    output = tmp_path / "reports"
    output.mkdir()
    report = output / filename
    report.write_text("existing report\n", encoding="utf-8")

    result = run_review(kind, source, output)

    assert result.returncode == 2
    assert metric in result.stderr
    assert "Traceback" not in result.stderr
    assert report.read_text(encoding="utf-8") == "existing report\n"
