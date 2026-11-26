from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(os.name != "posix", reason="The C locale must use ASCII for this regression.")

ROOT = Path(__file__).resolve().parents[1]


def _ascii_env() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "LC_ALL": "C",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONUTF8": "0",
    }


def _run(*args: str) -> None:
    result = subprocess.run(
        [sys.executable, *args], cwd=ROOT, env=_ascii_env(), capture_output=True
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")


@pytest.mark.parametrize("json_brief", [False, True])
def test_brand_pipeline_uses_utf8_files_in_ascii_locale(tmp_path: Path, json_brief: bool) -> None:
    html = tmp_path / "brand.html"
    html.write_text(
        '<title>Café</title><meta name="description" content="Crème">'
        '<h1>Élan</h1>',
        encoding="utf-8",
    )
    output = tmp_path / "output"
    common = ("--output-dir", str(output))
    _run(
        "-m", "codex_ads.cli", "dna", "--url", "https://brand.test",
        "--html-file", str(html), *common,
    )
    profile_path = output / "brand-profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["brand_name"] == "Café"
    # JSON produced by other tools may contain literal UTF-8, not ASCII escapes.
    profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"phases": ["acquisición"]}, ensure_ascii=False), encoding="utf-8")
    _run(
        "-m", "codex_ads.cli", "create", "--brand-profile", str(profile_path),
        "--context", str(context), *common,
    )
    brief = output / "campaign-brief.md"
    assert "Café" in brief.read_text(encoding="utf-8")
    assert "Crème" in brief.read_text(encoding="utf-8")
    assert "Acquisición" in brief.read_text(encoding="utf-8")
    brief_args = ("--brief", str(brief))
    if json_brief:
        brief = tmp_path / "brief.json"
        brief.write_text(json.dumps({"angles": ["Élan"]}, ensure_ascii=False), encoding="utf-8")
        brief_args = ("--brief-json", str(brief))
    _run(
        "-m", "codex_ads.cli", "generate", "--brand-profile", str(profile_path),
        *brief_args, *common,
    )
    prompts = (output / "ad-assets" / "asset-prompts.md").read_text(encoding="utf-8")
    assert "Café" in prompts
    if json_brief:
        assert "Élan" in prompts
    assets = list((output / "ad-assets").glob("*.svg"))
    assert len(assets) == 4
    for path in assets:
        assert "Café" in path.read_text(encoding="utf-8")
    _run("-m", "codex_ads.cli", "photoshoot", "--brand-profile", str(profile_path), *common)
    assert len(list((output / "ad-assets").glob("photoshoot-*.svg"))) == 5


def test_creative_writers_use_utf8_in_ascii_locale(tmp_path: Path) -> None:
    # Keep the subprocess source ASCII so its locale cannot hide encoding mistakes.
    script = r'''
import locale
from pathlib import Path
import sys
from codex_ads.creative import (
    build_campaign_brief, generate_asset_prompts, generate_photoshoot_set,
    write_brand_profile, write_campaign_brief,
)
assert locale.getpreferredencoding(False).lower() in {"ascii", "ansi_x3.4-1968"}
root = Path(sys.argv[1])
profile = {
    "brand_name": "Caf\u00e9",
    "description": "Cr\u00e8me",
    "tone_keywords": ["fiabilit\u00e9"],
    "color_palette": ["#123456"],
    "headline_themes": ["\u00c9lan"],
}
brief = build_campaign_brief(profile)
write_brand_profile(root, profile)
write_campaign_brief(root, brief)
generate_asset_prompts(root, profile, brief)
generate_photoshoot_set(root, profile, "Cr\u00e8me")
'''
    _run("-c", script, str(tmp_path))
    assert "Café" in (tmp_path / "campaign-brief.md").read_text(encoding="utf-8")
    prompts = (tmp_path / "ad-assets" / "asset-prompts.md").read_text(encoding="utf-8")
    assert "Élan" in prompts
    assert "fiabilité" in prompts
    assert "Café" in (tmp_path / "ad-assets" / "google-square.svg").read_text(encoding="utf-8")
    assert "Crème" in (tmp_path / "ad-assets" / "photoshoot-studio.svg").read_text(encoding="utf-8")
