from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from codex_ads.engine import audit_platform


# These values are seconds, counts, scores, days, or multiples rather than
# proportions, even when their numeric value happens to be between zero and one.
@pytest.mark.parametrize(
    "platform,metric",
    [
        ("youtube", "hook_seconds"),
        ("youtube", "native_format_count"),
        ("meta", "emq_score"),
        ("meta", "distinct_creatives"),
        ("google", "search_term_review_days"),
        ("linkedin", "audience_size"),
        ("linkedin", "creative_angles"),
        ("tiktok", "daily_budget_vs_cpa_multiple"),
        ("tiktok", "safe_zone_violations"),
        ("microsoft", "google_import_review_days"),
        ("microsoft", "partner_performance_review_days"),
        ("apple", "tap_coverage_count"),
    ],
)
@pytest.mark.parametrize("value,display", [(0.0, "0.00"), (0.5, "0.50"), (1.0, "1.00")])
def test_non_fraction_metrics_keep_their_numeric_units(platform, metric, value, display):
    result = audit_platform(platform, {"metrics": {metric: value}})
    finding = next(item for item in result["findings"] if item["metric"] == metric)
    assert finding["value"] == display
    assert finding["evidence"] == f"{metric}={value}"


@pytest.mark.parametrize(
    "platform,metric",
    [
        ("google", "wasted_spend_pct"),
        ("meta", "fatigue_index"),
        ("meta", "learning_limited_pct"),
        ("meta", "audience_overlap_pct"),
        ("youtube", "video_completion_rate"),
        ("linkedin", "form_completion_rate"),
        ("linkedin", "campaigns_under_min_budget_pct"),
        ("tiktok", "native_tiktok_ratio"),
        ("microsoft", "rsa_asset_coverage_pct"),
        ("apple", "cpp_coverage_pct"),
        ("apple", "search_match_broad_pct"),
    ],
)
@pytest.mark.parametrize("value,display", [(0, "0%"), (0.08, "8%"), (1, "100%"), (1.0, "100%")])
def test_fraction_metrics_use_percentages_for_integer_and_float_inputs(platform, metric, value, display):
    result = audit_platform(platform, {"metrics": {metric: value}})
    finding = next(item for item in result["findings"] if item["metric"] == metric)
    assert finding["value"] == display
    assert finding["evidence"] == f"{metric}={value}"


def test_boolean_and_missing_values_retain_their_existing_display():
    result = audit_platform("youtube", {"metrics": {"video_conversions_modeled": True}})
    findings = {item["metric"]: item for item in result["findings"]}
    assert findings["video_conversions_modeled"]["value"] == "True"
    assert findings["hook_seconds"]["value"] == "missing"
    assert findings["video_completion_rate"]["value"] == "missing"


def test_cli_preserves_metric_units_in_json_output(tmp_path):
    root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"metrics": {
        "hook_seconds": 0.5,
        "native_format_count": 1.0,
        "video_completion_rate": 1,
    }}))
    output = tmp_path / "output"
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "youtube", "--input", str(input_path), "--output-dir", str(output)],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    assert result.stderr == ""
    findings = {item["metric"]: item for item in json.loads((output / "youtube-audit.json").read_text())["findings"]}
    assert findings["hook_seconds"]["value"] == "0.50"
    assert findings["native_format_count"]["value"] == "1.00"
    assert findings["video_completion_rate"]["value"] == "100%"


@pytest.mark.parametrize("value,display", [(True, "True"), (-0.2, "-0.20"), (1.5, "1.50")])
def test_percent_display_preserves_existing_out_of_domain_values(value, display):
    # Formatting does not validate or silently coerce inputs. Metric validation
    # remains separate from the string value included in a finding.
    result = audit_platform("youtube", {"metrics": {"video_completion_rate": value}})
    finding = next(item for item in result["findings"] if item["metric"] == "video_completion_rate")
    assert finding["value"] == display


def test_numeric_representation_does_not_change_scoring():
    integer = audit_platform("youtube", {"metrics": {"native_format_count": 1, "video_completion_rate": 1}})
    decimal = audit_platform("youtube", {"metrics": {"native_format_count": 1.0, "video_completion_rate": 1.0}})
    assert integer["score"] == decimal["score"]
    for integer_finding, decimal_finding in zip(integer["findings"], decimal["findings"]):
        assert (integer_finding["id"], integer_finding["status"], integer_finding["score"]) == (
            decimal_finding["id"], decimal_finding["status"], decimal_finding["score"]
        )
