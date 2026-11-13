from __future__ import annotations

import json
import math
import sys

import pytest

from codex_ads.cli import main
from codex_ads.engine import build_generic_analysis


FIELDS = [
    ("creative", "creative_angles", "count"),
    ("creative", "fatigue_index", "fraction"),
    ("creative", "native_format_coverage", "fraction"),
    ("creative", "video_asset_share", "fraction"),
    ("landing", "message_match_score", "fraction"),
    ("landing", "mobile_lcp_seconds", "duration"),
    ("landing", "form_fields", "count"),
    ("landing", "trust_signal_count", "count"),
]


@pytest.mark.parametrize("kind, field, domain", FIELDS)
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "0.5", None])
def test_invalid_review_metrics_raise_field_error(kind, field, domain, value):
    with pytest.raises(ValueError, match=field):
        build_generic_analysis(kind, {"metrics": {field: value}})


@pytest.mark.parametrize("kind, field, domain", [item for item in FIELDS if item[2] != "duration"])
def test_metric_domain_is_enforced(kind, field, domain):
    value = 1.01 if domain == "fraction" else 1.5
    with pytest.raises(ValueError, match=field):
        build_generic_analysis(kind, {"metrics": {field: value}})


@pytest.mark.parametrize("kind, metrics", [
    ("creative", {"creative_angles": 1e308, "fatigue_index": 0, "native_format_coverage": 1, "video_asset_share": 1}),
    ("landing", {"mobile_lcp_seconds": 1e308, "form_fields": 1e308, "trust_signal_count": 1e308, "message_match_score": 1}),
])
def test_extreme_valid_counts_and_durations_keep_scores_finite(kind, metrics):
    result = build_generic_analysis(kind, {"metrics": metrics})
    assert math.isfinite(result["score"])
    assert 0 <= result["score"] <= 100
    assert all(0 <= value <= 100 for value in result["metrics"].values())


@pytest.mark.parametrize("kind, expected", [
    ("creative", {"variety": 60, "fatigue": 60, "native_fit": 70, "video_mix": 50}),
    ("landing", {"message_match": 70, "speed": 58, "form_friction": 40, "trust": 60}),
])
def test_default_review_scores_remain_compatible(kind, expected):
    assert build_generic_analysis(kind, {})["metrics"] == expected


@pytest.mark.parametrize("kind, field", [("creative", "fatigue_index"), ("landing", "message_match_score")])
def test_invalid_cli_review_does_not_create_report(tmp_path, monkeypatch, kind, field):
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"metrics": {field: 2}}))
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", ["codex-ads", kind, "--input", str(source), "--output-dir", str(output)])
    with pytest.raises(ValueError, match=field):
        main()
    assert not output.exists()
