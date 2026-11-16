from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.engine import build_generic_analysis


def review(spend: dict) -> dict:
    return build_generic_analysis('budget', {'spend': spend})


def test_balanced_allocation_has_bounded_score_and_strong_status() -> None:
    result = review({'search': 500, 'social': 500})
    assert result['score'] == 100
    assert result['status'] == 'strong'
    assert result['metrics'] == {'search': 50.0, 'social': 50.0}
    assert 'balanced' in result['priorities'][0]


@pytest.mark.parametrize('spend', [{}, {'search': 0}, {'search': 0, 'social': 0}])
def test_absent_spend_is_insufficient_data_not_a_balanced_allocation(spend: dict) -> None:
    result = review(spend)
    assert result['score'] is None
    assert result['status'] == 'insufficient-data'
    assert not any('balanced' in item for item in result['priorities'])
    assert all(value == 0 for value in result['metrics'].values())


def test_numeric_strings_are_normalized_before_share_calculation() -> None:
    result = review({'search': '750', 'social': '250.0'})
    assert result['metrics'] == {'search': 75.0, 'social': 25.0}
    assert result['status'] == 'watch'
    assert 0 <= result['score'] < 100
    assert 'search' in result['priorities'][0]


@pytest.mark.parametrize('value', [-1, '-2', True, None, [], {}, 'bad', float('nan'), float('inf'), '-inf', 10**400])
def test_invalid_spend_has_field_specific_error(value: object) -> None:
    with pytest.raises(ValueError, match=r'spend\.search'):
        review({'search': value})


@pytest.mark.parametrize('spend', [None, [], 42])
def test_spend_must_be_a_mapping(spend: object) -> None:
    with pytest.raises(ValueError, match='spend'):
        build_generic_analysis('budget', {'spend': spend})


def test_overflowing_total_has_explicit_error() -> None:
    with pytest.raises(ValueError, match='total spend'):
        review({'search': 1e308, 'social': 1e308})


def test_many_small_channels_cannot_produce_negative_score() -> None:
    result = review({f'channel-{i}': 1 for i in range(100)})
    assert result['score'] == 0
    assert result['status'] == 'watch'
    assert sum(result['metrics'].values()) == 100


def test_large_finite_amount_retains_a_finite_share() -> None:
    result = review({'search': 1e308, 'social': 0})
    assert result['metrics'] == {'search': 100.0, 'social': 0.0}
    assert 0 <= result['score'] <= 100


def test_budget_cli_rejects_invalid_spend_without_creating_report(tmp_path: Path) -> None:
    source = tmp_path / 'input.json'
    source.write_text(json.dumps({'spend': {'search': -1}}))
    output = tmp_path / 'output'
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-m', 'codex_ads.cli', 'budget', '--input', str(source), '--output-dir', str(output)],
        env={**os.environ, 'PYTHONPATH': str(root / 'src')}, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert 'spend.search' in result.stderr
    assert not output.exists()


def test_budget_cli_reports_missing_data_truthfully(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-m', 'codex_ads.cli', 'budget', '--output-dir', str(tmp_path)],
        env={**os.environ, 'PYTHONPATH': str(root / 'src')}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    report = (tmp_path / 'ADS-BUDGET-REVIEW.md').read_text()
    assert 'insufficient-data' in report
    assert 'balanced' not in report
