from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from codex_ads.creative import extract_brand_dna


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PALETTE = ["#0b6e4f", "#1f2937", "#f4f6f8"]


@pytest.mark.parametrize("color", ["#AbC", "#AbCd", "#AbCdEf", "#AbCdEf12"])
def test_complete_css_hex_colors_keep_their_components(color):
    profile = extract_brand_dna("https://brand.test", f"<style>body{{color:{color}}}</style>")
    assert profile["color_palette"] == [color.lower()]


@pytest.mark.parametrize("token", [
    "#12", "#12345", "#1234567", "#123456789", "#123456789abc",
    "#abcg", "#abcdefghi", "#abc_color", "#abcdef-more",
])
def test_invalid_or_longer_tokens_do_not_supply_partial_colors(token):
    profile = extract_brand_dna("https://brand.test", f"<style>body{{color:{token}}}</style>")
    assert profile["color_palette"] == DEFAULT_PALETTE


def test_palette_stays_sorted_unique_and_capped_at_eight():
    colors = [f"#{number:06x}" for number in range(10)]
    html = "<style>body{color:#ABCDEF;background:#abcdef}" + " ".join(reversed(colors)) + "</style>"
    assert extract_brand_dna("https://brand.test", html)["color_palette"] == colors[:8]


def test_existing_six_digit_colors_and_empty_fallback_remain_compatible():
    html = '<style>body{color:#ABCDEF;background:#123456}</style>'
    assert extract_brand_dna("https://brand.test", html)["color_palette"] == ["#123456", "#abcdef"]
    assert extract_brand_dna("https://brand.test", "<title>Brand</title>")["color_palette"] == DEFAULT_PALETTE


def test_dna_to_generated_svg_preserves_shorthand_and_alpha_colors(tmp_path):
    html_path = tmp_path / "brand.html"
    html_path.write_text("<title>Brand</title><style>body{color:#ABC;background:#1234;border-color:#56789ABC}</style>")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))

    def run_cli(*args):
        return subprocess.run(
            [sys.executable, "-m", "codex_ads.cli", *args], cwd=ROOT,
            env=env, text=True, capture_output=True, check=True,
        )

    run_cli("dna", "--url", "https://brand.test", "--html-file", str(html_path), "--output-dir", str(tmp_path))
    profile_path = tmp_path / "brand-profile.json"
    palette = ["#1234", "#56789abc", "#abc"]
    assert json.loads(profile_path.read_text())["color_palette"] == palette
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps({"angles": ["proof"]}))
    run_cli("generate", "--brand-profile", str(profile_path), "--brief-json", str(brief_path), "--output-dir", str(tmp_path))
    for svg_path in (tmp_path / "ad-assets").glob("*.svg"):
        svg = ET.parse(svg_path).getroot()
        assert [node.attrib["fill"] for node in svg] == [palette[0], palette[1], palette[2], palette[2]]
    assert len(list((tmp_path / "ad-assets").glob("*.svg"))) == 4
