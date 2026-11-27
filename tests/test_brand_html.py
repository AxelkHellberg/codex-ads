from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codex_ads.creative import build_campaign_brief, extract_brand_dna, write_brand_profile, write_campaign_brief


@pytest.mark.parametrize("meta", [
    '<meta content="Fresh &amp; fast" name="description">',
    '<META NAME="DESCRIPTION" CONTENT="Fresh &amp; fast">',
    "<meta content='Fresh &amp; fast' data-x='1' name='description' />",
    "<meta name=description content='Fresh &amp; fast'>",
])
def test_meta_attribute_order_case_and_quoting_are_equivalent(meta):
    result = extract_brand_dna("https://brand.test", meta)
    assert result["description"] == "Fresh & fast"


def test_title_and_headings_are_readable_text():
    result = extract_brand_dna("https://brand.test", '<title data-x="1">  Fish &amp; Chips &#169; </title><h1>Fresh <em>food</em> &amp; fast</h1><h2>One<br>two</h2>')
    assert result["brand_name"] == "Fish & Chips ©"
    assert result["headline_themes"] == ["Fresh food & fast", "One two"]


def test_first_title_description_and_six_heading_limit_are_preserved():
    html = '<title>First</title><title>Second</title><meta name="description" content="First"><meta name="description" content="Second">'
    html += "".join(f"<h2>Heading {i}</h2>" for i in range(8))
    result = extract_brand_dna("https://brand.test", html)
    assert result["brand_name"] == "First"
    assert result["description"] == "First"
    assert result["headline_themes"] == [f"Heading {i}" for i in range(6)]


def test_script_style_and_comments_do_not_supply_brand_copy():
    result = extract_brand_dna("https://brand.test", '<!-- <title>Fake</title><h1>Fake</h1> --><script>const copy = "premium growth smart";</script><style>.performance { color: red; }</style><h1>Trusted service</h1>')
    assert result["brand_name"] == "brand.test"
    assert result["headline_themes"] == ["Trusted service"]
    assert result["tone_keywords"] == ["trusted"]


def test_missing_or_blank_title_uses_host():
    for html in ["", "<title> </title>"]:
        result = extract_brand_dna("https://brand.test/page", html)
        assert result["brand_name"] == "brand.test"
        assert result["description"] == ""
        assert result["headline_themes"] == []


def test_decoded_copy_reaches_profile_and_campaign_brief(tmp_path):
    profile = extract_brand_dna("https://brand.test", '<title>Fish &amp; Chips</title><meta content="Fresh &amp; fast" name="description"><h1>Fresh <em>food</em></h1>')
    profile_path = write_brand_profile(tmp_path, profile)
    assert json.loads(profile_path.read_text())["brand_name"] == "Fish & Chips"
    brief = build_campaign_brief(profile)
    brief_path = write_campaign_brief(tmp_path, brief)
    text = brief_path.read_text()
    assert "# Campaign Brief: Fish & Chips" in text
    assert "- Positioning: Fresh & fast" in text
    assert "- Fresh food" in text
    assert "&amp;" not in text
    assert "<em>" not in text


@pytest.mark.parametrize("html, expected", [
    ("<p>pre<strong>mium</strong> service</p>", ["premium"]),
    ("<p>per<em>for<span>mance</span></em> matters</p>", ["performance"]),
    ("<p><a href='/'>tru</a>sted service</p>", ["trusted"]),
    ("<p>pre<!-- annotation -->mium service</p>", ["premium"]),
    ("<p>pre<script>smart growth</script>mium service</p>", ["premium"]),
    ("<p>pre<style>.smart { color: red }</style>mium service</p>", ["premium"]),
    ("<p><span>fast</span>er trusted service</p>", ["trusted"]),
    ("<p>premium<span>ize</span> trusted service</p>", ["trusted"]),
    ("<p>smart<span>er</span> <em>performance</em>s trusted service</p>", ["trusted"]),
])
def test_tone_keywords_follow_visible_inline_text(html, expected):
    assert extract_brand_dna("https://brand.test", html)["tone_keywords"] == expected


@pytest.mark.parametrize("html", [
    "<p>fast</p><p>growth</p>",
    "<div>fast</div><div>growth</div>",
    "<h1>fast</h1><h2>growth</h2>",
    "<ul><li>fast</li><li>growth</li></ul>",
    "<table><tr><td>fast</td><td>growth</td></tr></table>",
    "<blockquote>fast</blockquote>growth",
    "<section>fast</section>growth",
    "fast<br>growth",
    "fast<br/>growth",
    "fast<hr>growth",
    "<title>fast</title>growth",
    "<span>fast </span><em>growth</em>",
    "<span>fast</span> <em>growth</em>",
    "fast&nbsp;growth",
])
def test_separate_visible_words_keep_their_boundaries(html):
    assert extract_brand_dna("https://brand.test", html)["tone_keywords"] == ["fast", "growth"]


def test_inline_tone_text_reaches_the_cli_profile_and_campaign(tmp_path):
    root = Path(__file__).resolve().parents[1]
    html = tmp_path / "brand.html"
    html.write_text(
        "<title>Brand</title><h1>pre<strong>mium</strong> service</h1>"
        "<p>per<em>formance</em> from a <span>tru</span>sted team</p>",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "dna", "--url", "https://brand.test",
         "--html-file", str(html), "--output-dir", str(output)],
        cwd=root, env=env, check=True, capture_output=True, text=True, timeout=30,
    )
    profile_path = output / "brand-profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["tone_keywords"] == ["performance", "premium", "trusted"]
    assert profile["headline_themes"] == ["premium service"]

    subprocess.run(
        [sys.executable, "-m", "codex_ads.cli", "create", "--brand-profile", str(profile_path),
         "--output-dir", str(output)],
        cwd=root, env=env, check=True, capture_output=True, text=True, timeout=30,
    )
    brief = (output / "campaign-brief.md").read_text(encoding="utf-8")
    assert "- Tone: performance, premium, trusted" in brief
    assert "Brand delivers performance, premium, trusted outcomes" in brief
