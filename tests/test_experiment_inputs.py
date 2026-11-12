import math

import pytest

from codex_ads.engine import compute_ab_test


@pytest.mark.parametrize('field,value', [
    ('baseline_rate', 0), ('baseline_rate', 1), ('baseline_rate', -0.1),
    ('baseline_rate', True), ('baseline_rate', 'bad'), ('baseline_rate', math.nan),
    ('baseline_rate', math.inf), ('baseline_rate', None),
    ('minimum_detectable_effect', 0), ('minimum_detectable_effect', -0.1),
    ('minimum_detectable_effect', True), ('minimum_detectable_effect', math.inf),
    ('minimum_detectable_effect', math.nan), ('minimum_detectable_effect', []),
    ('weekly_visitors', 0), ('weekly_visitors', -1), ('weekly_visitors', 1.5),
    ('weekly_visitors', True), ('weekly_visitors', '1.5'), ('weekly_visitors', None),
    ('weekly_visitors', math.inf), ('weekly_visitors', math.nan),
])
def test_invalid_experiment_input_has_a_field_error(field, value):
    with pytest.raises(ValueError, match=field):
        compute_ab_test({field: value})


def test_impossible_relative_uplift_is_rejected():
    with pytest.raises(ValueError, match='minimum_detectable_effect'):
        compute_ab_test({'baseline_rate': .8, 'minimum_detectable_effect': .5})


@pytest.mark.parametrize('payload', [
    {'baseline_rate': 1e-300},
    {'minimum_detectable_effect': 1e-300},
])
def test_unrepresentable_sample_size_has_a_clear_error(payload):
    with pytest.raises(ValueError, match='numerical range'):
        compute_ab_test(payload)


def test_default_and_numeric_string_inputs_keep_existing_plan():
    result = compute_ab_test({})
    expected = max(1000, int(16 * .03 * (1 - .03) / (.03 * .15) ** 2))
    assert result['sample_per_variant'] == expected
    assert result['estimated_duration_weeks'] == math.ceil(2 * expected / 10000)
    assert compute_ab_test({'baseline_rate': '0.03', 'minimum_detectable_effect': '0.15', 'weekly_visitors': '10000'}) == result


def test_valid_high_rate_keeps_minimum_sample_size():
    result = compute_ab_test({'baseline_rate': .5, 'minimum_detectable_effect': 1, 'weekly_visitors': 1000})
    assert result['sample_per_variant'] == 1000
    assert result['estimated_duration_weeks'] == 2
