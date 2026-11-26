from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(os.name != "posix", reason="The C locale must use ASCII for this regression.")

ROOT = Path(__file__).resolve().parents[1]


def _run_ascii(*args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "LC_ALL": "C",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONUTF8": "0",
    }
    result = subprocess.run(
        [sys.executable, *args], cwd=ROOT, env=env, capture_output=True
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return result


def _input(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_audit_bundle_uses_utf8_in_ascii_locale(tmp_path: Path) -> None:
    source = _input(tmp_path / "audit.json", {"goal": "café", "platforms": {}})
    output = tmp_path / "audit"
    _run_ascii("-m", "codex_ads.cli", "audit", "--input", str(source), "--output-dir", str(output))
    report = (output / "ADS-AUDIT-REPORT.md").read_text(encoding="utf-8")
    assert "café" in report
    summary = json.loads((output / "ads-audit-summary.json").read_text(encoding="utf-8"))
    assert summary["goal"] == "café"
    assert (output / "ADS-ACTION-PLAN.md").is_file()
    assert (output / "ADS-QUICK-WINS.md").is_file()


def test_analysis_uses_utf8_in_ascii_locale(tmp_path: Path) -> None:
    source = _input(tmp_path / "competitor.json", {
        "competitors": [{"name": "Café", "gaps": ["coût"], "opportunities": ["Élan"]}],
    })
    output = tmp_path / "competitor"
    _run_ascii("-m", "codex_ads.cli", "competitor", "--input", str(source), "--output-dir", str(output))
    report = (output / "ADS-COMPETITOR.md").read_text(encoding="utf-8")
    assert "Café: close gaps in coût." in report
    assert "Café: exploit whitespace in Élan." in report


def test_pdf_reads_utf8_summary_in_ascii_locale(tmp_path: Path) -> None:
    source = _input(tmp_path / "summary.json", {"business_type": "saas", "goal": "café", "platforms": []})
    output = tmp_path / "report"
    _run_ascii("-m", "codex_ads.cli", "report", "--summary", str(source), "--output-dir", str(output))
    assert (output / "ADS-REPORT.pdf").read_bytes().startswith(b"%PDF-")
