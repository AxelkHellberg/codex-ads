from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.engine import build_portfolio_audit
from codex_ads.reporting import build_pdf_report


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = {"label": "Google Ads", "score": 85, "grade": "B"}
FINDING = {"id": "G01", "severity": "high", "title": "Tracking", "recommendation": "Check events"}
INVALID_SUMMARIES = [
    (None, "summary"),
    ([], "summary"),
    ("summary", "summary"),
    ({"platforms": None}, "summary.platforms"),
    ({"platforms": "google"}, "summary.platforms"),
    ({"platforms": {}}, "summary.platforms"),
    ({"platforms": [None]}, "summary.platforms[0]"),
    ({"platforms": ["google"]}, "summary.platforms[0]"),
    *[({"platforms": [{key: value for key, value in PLATFORM.items() if key != missing}]},
       f"summary.platforms[0].{missing}") for missing in PLATFORM],
    ({"platforms": [{**PLATFORM, "findings": None}]}, "summary.platforms[0].findings"),
    ({"platforms": [{**PLATFORM, "findings": "needs work"}]}, "summary.platforms[0].findings"),
    ({"platforms": [{**PLATFORM, "findings": {}}]}, "summary.platforms[0].findings"),
    ({"platforms": [{**PLATFORM, "findings": [None]}]}, "summary.platforms[0].findings[0]"),
    *[({"platforms": [{**PLATFORM, "findings": [
        {key: value for key, value in FINDING.items() if key != missing}]}]},
       f"summary.platforms[0].findings[0].{missing}") for missing in FINDING],
    ({"platforms": [PLATFORM, {**PLATFORM, "findings": [FINDING] * 5 + [None]}]},
     "summary.platforms[1].findings[5]"),
]


@pytest.mark.parametrize("summary, field", INVALID_SUMMARIES)
def test_invalid_summary_is_rejected_before_creating_output(tmp_path, summary, field):
    source = tmp_path / "summary.json"
    source.write_text(json.dumps(summary))
    output = tmp_path / "report"

    with pytest.raises(ValueError) as error:
        build_pdf_report(source, output)

    assert str(error.value).startswith(field + " ")
    assert not output.exists()


@pytest.mark.parametrize("summary, field", [
    (None, "summary"),
    ({"platforms": "google"}, "summary.platforms"),
    ({"platforms": [{"label": "Google Ads", "grade": "B"}]}, "summary.platforms[0].score"),
    ({"platforms": [{**PLATFORM, "findings": "needs work"}]}, "summary.platforms[0].findings"),
    ({"platforms": [{**PLATFORM, "findings": [None]}]}, "summary.platforms[0].findings[0]"),
    ({"platforms": [{**PLATFORM, "findings": [{"id": "G01", "severity": "high"}]}]},
     "summary.platforms[0].findings[0].title"),
    ({"platforms": [PLATFORM, {**PLATFORM, "findings": [FINDING] * 5 + [None]}]},
     "summary.platforms[1].findings[5]"),
])
def test_report_cli_explains_invalid_summary_without_writing(tmp_path, summary, field):
    source = tmp_path / "summary.json"
    source.write_text(json.dumps(summary))
    output = tmp_path / "report"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "report", "--summary", str(source),
         "--output-dir", str(output)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True, timeout=10,
    )

    assert result.returncode == 2
    assert field in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


def test_invalid_summary_preserves_existing_report(tmp_path):
    source = tmp_path / "summary.json"
    source.write_text(json.dumps({"platforms": [{**PLATFORM, "findings": [FINDING, {}]}]}))
    report = tmp_path / "ADS-REPORT.pdf"
    report.write_bytes(b"previous report")

    with pytest.raises(ValueError, match="recommendation|id"):
        build_pdf_report(source, tmp_path)

    assert report.read_bytes() == b"previous report"


@pytest.mark.parametrize("summary", [{}, {"platforms": []}, {"platforms": [PLATFORM]},
                                    {"platforms": [{**PLATFORM, "findings": []}]}])
def test_optional_summary_lists_keep_their_defaults(tmp_path, summary):
    source = tmp_path / "summary.json"
    source.write_text(json.dumps(summary))

    report = build_pdf_report(source, tmp_path / "report")

    assert report.read_bytes().startswith(b"%PDF-")


def test_report_accepts_generated_audit_summary(tmp_path):
    payload = json.loads((ROOT / "tests/fixtures/sample_portfolio.json").read_text())
    source = tmp_path / "summary.json"
    source.write_text(json.dumps(build_portfolio_audit(payload)))

    report = build_pdf_report(source, tmp_path / "report")

    assert report.read_bytes().startswith(b"%PDF-")
