from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.engine import build_generic_analysis


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("payload", [None, [], "Example"])
def test_competitor_input_must_be_an_object(payload) -> None:
    with pytest.raises(ValueError, match="competitor input must be an object"):
        build_generic_analysis("competitor", payload)


def test_valid_competitor_lists_preserve_text_and_scoring() -> None:
    analysis = build_generic_analysis("competitor", {"competitors": [
        {"name": "Example", "gaps": ["proof", "  message match  "],
         "opportunities": ["Rétention"]},
        {"name": "Other", "opportunities": ["video", "search"]},
    ]})
    assert analysis["metrics"] == {"competitors_reviewed": 2, "opportunities": 3, "gaps": 2}
    assert analysis["score"] == 71
    assert analysis["status"] == "watch"
    assert analysis["priorities"] == [
        "Example: close gaps in proof,   message match  .",
        "Example: exploit whitespace in Rétention.",
        "Other: exploit whitespace in video, search.",
    ]


@pytest.mark.parametrize("payload", [{}, {"competitors": []}, {"competitors": [{"name": "Example"}]}])
def test_empty_competitor_findings_keep_existing_fallback(payload) -> None:
    analysis = build_generic_analysis("competitor", payload)
    assert analysis["metrics"]["gaps"] == analysis["metrics"]["opportunities"] == 0
    assert analysis["score"] == 60
    assert analysis["priorities"] == [
        "Capture competitor messaging, offers, and placements before making a recommendation."
    ]


@pytest.mark.parametrize("competitors", [None, "Example", {"name": "Example"}, True])
def test_competitors_must_be_a_list(competitors) -> None:
    with pytest.raises(ValueError, match="competitors must be a list of objects"):
        build_generic_analysis("competitor", {"competitors": competitors})


@pytest.mark.parametrize("competitor", [None, "Example", ["Example"], 1])
def test_competitor_entries_must_be_objects(competitor) -> None:
    with pytest.raises(ValueError, match=r"competitors\[0\] must be an object"):
        build_generic_analysis("competitor", {"competitors": [competitor]})


@pytest.mark.parametrize("name", [None, "", " \t", 1])
def test_competitor_names_must_be_nonblank_strings(name) -> None:
    with pytest.raises(ValueError, match=r"competitors\[0\].name must be a nonblank string"):
        build_generic_analysis("competitor", {"competitors": [{"name": name}]})


@pytest.mark.parametrize("field", ["gaps", "opportunities"])
@pytest.mark.parametrize("value", ["proof", None, {"proof": True}, [""], [" \t"], ["proof", 1]])
def test_findings_must_be_lists_of_nonblank_strings(field, value) -> None:
    with pytest.raises(ValueError, match=rf"competitors\[0\].{field} must be a list of nonblank strings"):
        build_generic_analysis("competitor", {"competitors": [{"name": "Example", field: value}]})


def run_competitor_cli(tmp_path: Path, payload) -> tuple[subprocess.CompletedProcess, Path]:
    input_path = tmp_path / "competitors.json"
    input_path.write_text(json.dumps(payload))
    output_path = tmp_path / "output"
    result = subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "competitor", "--input", str(input_path),
         "--output-dir", str(output_path)],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True,
    )
    return result, output_path


@pytest.mark.parametrize("payload,field", [
    ({"competitors": [{"name": "Example", "gaps": "proof"}]}, "competitors[0].gaps"),
    ({"competitors": [{"name": "Example", "opportunities": ["proof", 1]}]}, "competitors[0].opportunities"),
    ({"competitors": [{"gaps": ["proof"]}]}, "competitors[0].name"),
    ({"competitors": None}, "competitors"),
    ([], "competitor input"),
])
def test_cli_rejects_invalid_competitors_before_creating_output(tmp_path: Path, payload, field) -> None:
    result, output_path = run_competitor_cli(tmp_path, payload)
    assert result.returncode == 2
    assert field in result.stderr
    assert "Traceback" not in result.stderr
    assert not output_path.exists()


def test_cli_writes_valid_competitor_findings(tmp_path: Path) -> None:
    result, output_path = run_competitor_cli(tmp_path, {"competitors": [
        {"name": "Example", "gaps": ["proof"], "opportunities": ["speed"]}
    ]})
    assert result.returncode == 0, result.stderr
    report = (output_path / "ADS-COMPETITOR.md").read_text()
    assert "- gaps: `1`" in report
    assert "- opportunities: `1`" in report
    assert "Example: close gaps in proof." in report
    assert "Example: exploit whitespace in speed." in report
