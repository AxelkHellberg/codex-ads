from __future__ import annotations

import json
import math

import pytest

from codex_ads.engine import compute_math_model


@pytest.mark.parametrize("field", ["spend", "clicks", "conversions", "revenue", "ltv", "gross_margin"])
@pytest.mark.parametrize("value", [True, False, None, [], {}, "bad", float("nan"), float("inf"), "-Infinity", 10**400])
def test_invalid_inputs_are_rejected_with_the_field_name(field, value):
    with pytest.raises(ValueError, match=field):
        compute_math_model({field: value})


@pytest.mark.parametrize("field", ["spend", "clicks", "conversions", "revenue", "ltv", "gross_margin"])
def test_negative_inputs_are_rejected(field):
    with pytest.raises(ValueError, match=field):
        compute_math_model({field: -1})


def test_margin_is_a_fraction():
    with pytest.raises(ValueError, match="gross_margin"):
        compute_math_model({"gross_margin": 1.01})


def test_numeric_strings_keep_the_existing_formulas():
    result = compute_math_model({"spend": "100", "clicks": "50", "conversions": "4", "revenue": "300", "gross_margin": "0.5", "ltv": "200"})
    assert result == {"spend": 100.0, "clicks": 50.0, "conversions": 4.0, "revenue": 300.0, "cpc": 2.0, "cpa": 25.0, "roas": 3.0, "break_even_cpa": 37.5, "ltv_cac": 8.0}


@pytest.mark.parametrize("payload", [{}, {"conversions": 2}, {"spend": 10}, {"spend": 10, "conversions": 0.5}, {"gross_margin": 0}, {"gross_margin": 1}])
def test_zero_denominators_and_fractional_attribution_remain_supported(payload):
    result = compute_math_model(payload)
    json.dumps(result, allow_nan=False)
    assert all(value is None or math.isfinite(value) for value in result.values())
    assert (result["cpa"] is None) == (not payload.get("conversions", 0))


@pytest.mark.parametrize("payload, metric", [
    ({"spend": 1e308, "clicks": 1e-308}, "cpc"),
    ({"spend": 1e308, "conversions": 1e-308}, "cpa"),
    ({"spend": 1e-308, "revenue": 1e308}, "roas"),
    ({"revenue": 1e308, "conversions": 1e-308}, "break_even_cpa"),
    ({"spend": 1e-308, "conversions": 1, "ltv": 1e308}, "ltv_cac"),
])
def test_overflowing_ratios_do_not_reach_output(payload, metric):
    with pytest.raises(ValueError, match=metric):
        compute_math_model(payload)
