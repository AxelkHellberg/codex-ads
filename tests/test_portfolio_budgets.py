import copy
import math

import pytest

from codex_ads.engine import audit_platform, build_portfolio_audit


def test_string_budgets_are_normalized_without_mutating_input():
    payload = {'monthly_budget': '400', 'platforms': {
        'google': {'budget': '100', 'metrics': {'conversion_tracking_enabled': True}},
        'meta': {'budget': '300', 'metrics': {'pixel_or_capi_live': False}},
    }}
    original = copy.deepcopy(payload)
    result = build_portfolio_audit(payload)
    google, meta = result['platforms']
    assert [google['budget'], meta['budget']] == [100.0, 300.0]
    assert [google['budget_share'], meta['budget_share']] == [0.25, 0.75]
    assert result['score'] == round(google['score'] * .25 + meta['score'] * .75, 1)
    assert result['monthly_budget'] == 400.0
    assert payload == original


@pytest.mark.parametrize('value', [-1, '-1', True, None, '', 'not a budget', [], {}, math.inf, -math.inf, math.nan, 'NaN', 'Infinity', 10**400])
def test_invalid_platform_budget_fails_before_aggregation(value):
    with pytest.raises(ValueError, match='google.budget'):
        build_portfolio_audit({'platforms': {'google': {'budget': value}}})
    with pytest.raises(ValueError, match='google.budget'):
        audit_platform('google', {'budget': value})


@pytest.mark.parametrize('value', [-1, True, math.nan, 'Infinity', None])
def test_invalid_monthly_budget_is_rejected_even_without_platforms(value):
    with pytest.raises(ValueError, match='monthly_budget'):
        build_portfolio_audit({'monthly_budget': value})


def test_zero_budgets_keep_equal_weight_fallback():
    result = build_portfolio_audit({'platforms': {'google': {}, 'meta': {'budget': '0'}}})
    assert [p['budget_share'] for p in result['platforms']] == [.5, .5]
    assert result['monthly_budget'] == 0
    assert math.isfinite(result['score'])


def test_one_zero_budget_gets_no_weight_when_other_budget_is_positive():
    result = build_portfolio_audit({'platforms': {'google': {'budget': 0}, 'meta': {'budget': 10}}})
    assert [p['budget_share'] for p in result['platforms']] == [0, 1]
    assert result['score'] == result['platforms'][1]['score']


def test_overflowing_budget_total_is_rejected():
    with pytest.raises(ValueError, match='total platform budget'):
        build_portfolio_audit({'platforms': {'google': {'budget': 1e308}, 'meta': {'budget': 1e308}}})
