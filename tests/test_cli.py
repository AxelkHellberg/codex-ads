from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH_ENV = {"PYTHONPATH": str(ROOT / "src"), **os.environ}


def run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", *args],
        cwd=ROOT,
        env=PYTHONPATH_ENV,
        text=True,
        capture_output=True,
        check=True,
    )


def test_audit_bundle_and_report(tmp_path: Path) -> None:
    fixture = ROOT / "tests" / "fixtures" / "sample_portfolio.json"
    run_cli(tmp_path, "audit", "--input", str(fixture), "--output-dir", str(tmp_path))
    summary = tmp_path / "ads-audit-summary.json"
    assert summary.exists()
    data = json.loads(summary.read_text())
    assert data["score"] > 0
    assert (tmp_path / "ADS-AUDIT-REPORT.md").exists()
    assert (tmp_path / "ADS-ACTION-PLAN.md").exists()
    assert (tmp_path / "ADS-QUICK-WINS.md").exists()

    run_cli(tmp_path, "report", "--summary", str(summary), "--output-dir", str(tmp_path))
    assert (tmp_path / "ADS-REPORT.pdf").exists()


def test_brand_pipeline(tmp_path: Path) -> None:
    html = ROOT / "tests" / "fixtures" / "sample_brand.html"
    run_cli(tmp_path, "dna", "--url", "https://northstar.test", "--html-file", str(html), "--output-dir", str(tmp_path))
    profile = tmp_path / "brand-profile.json"
    assert profile.exists()

    run_cli(tmp_path, "create", "--brand-profile", str(profile), "--output-dir", str(tmp_path))
    brief = tmp_path / "campaign-brief.md"
    assert brief.exists()

    run_cli(tmp_path, "generate", "--brand-profile", str(profile), "--brief", str(brief), "--output-dir", str(tmp_path))
    assert (tmp_path / "ad-assets" / "asset-manifest.json").exists()
    assert any(path.suffix == ".svg" for path in (tmp_path / "ad-assets").iterdir())

    run_cli(tmp_path, "photoshoot", "--brand-profile", str(profile), "--product-name", "Northstar Box", "--output-dir", str(tmp_path))
    assert (tmp_path / "ad-assets" / "photoshoot-prompts.json").exists()


def test_math_and_test_utilities(tmp_path: Path) -> None:
    math_fixture = ROOT / "tests" / "fixtures" / "sample_math.json"
    test_fixture = ROOT / "tests" / "fixtures" / "sample_test.json"
    run_cli(tmp_path, "math", "--input", str(math_fixture), "--output-dir", str(tmp_path))
    run_cli(tmp_path, "test", "--input", str(test_fixture), "--output-dir", str(tmp_path))
    assert (tmp_path / "ADS-MATH.md").exists()
    assert (tmp_path / "ADS-TEST-PLAN.md").exists()
