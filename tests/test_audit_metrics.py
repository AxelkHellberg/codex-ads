import math

import pytest

from codex_ads.engine import PLATFORM_CONFIG, audit_platform, build_portfolio_audit


@pytest.mark.parametrize('value', ['false', 'true', 0, 1, [], {}, float('nan')])
def test_non_boolean_tracking_does_not_pass(value):
    result = audit_platform('google', {'metrics': {'conversion_tracking_enabled': value}})
    finding = next(item for item in result['findings'] if item['id'] == 'G01')
    assert finding['status'] == 'warning'
    assert finding['score'] == 45
    assert 'JSON boolean' in finding['evidence']


@pytest.mark.parametrize('value', ['false', 0, [], {}])
def test_non_boolean_negative_rule_does_not_pass(value):
    result = audit_platform('google', {'metrics': {'broad_match_manual_cpc': value}})
    finding = next(item for item in result['findings'] if item['id'] == 'G05')
    assert finding['status'] == 'warning'
    assert 'JSON boolean' in finding['evidence']


@pytest.mark.parametrize('value', ['0.02', True, [], {}, math.nan, math.inf, -math.inf, 10**400])
@pytest.mark.parametrize('platform,metric,rule_id', [('google', 'wasted_spend_pct', 'G03'), ('meta', 'emq_score', 'M02')])
def test_invalid_numeric_metric_is_a_warning(platform, metric, rule_id, value):
    result = audit_platform(platform, {'metrics': {metric: value}})
    finding = next(item for item in result['findings'] if item['id'] == rule_id)
    assert finding['status'] == 'warning'
    assert finding['score'] == 45
    assert 'finite JSON number' in finding['evidence']


def test_typed_values_keep_existing_rule_results():
    result = audit_platform('google', {'metrics': {
        'conversion_tracking_enabled': False,
        'enhanced_conversions_enabled': True,
        'broad_match_manual_cpc': False,
        'wasted_spend_pct': 0.08,
        'search_term_review_days': 30,
    }})
    findings = {item['id']: item for item in result['findings']}
    assert findings['G01']['status'] == 'fail'
    assert findings['G02']['status'] == 'pass'
    assert findings['G05']['status'] == 'pass'
    assert findings['G03']['status'] == 'warning'
    assert findings['G06']['status'] == 'fail'
    assert findings['G04']['status'] == 'warning'
    assert 'missing' in findings['G04']['evidence'].lower()


def test_portfolio_invalid_metric_is_actionable_without_aborting():
    result = build_portfolio_audit({'platforms': {'google': {'metrics': {
        'conversion_tracking_enabled': 'false', 'wasted_spend_pct': 'unknown',
    }}}})
    platform = result['platforms'][0]
    assert math.isfinite(result['score'])
    assert any(item['id'] == 'G01' for item in platform['quick_wins'])
    assert all(item['status'] == 'warning' for item in platform['findings'])
