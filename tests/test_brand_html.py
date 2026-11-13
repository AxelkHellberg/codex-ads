from __future__ import annotations

import json

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
