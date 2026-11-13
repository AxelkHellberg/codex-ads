from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from codex_ads.creative import _placeholder_asset, generate_asset_prompts, generate_photoshoot_set


NS = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("title, subtitle", [
    ("Fish & Chips <Co>", "Save <now> & enjoy"),
    ('Tea "Time"', "L'été > winter"),
    ("<tspan>literal</tspan>", "&#65; &amp; literal"),
    ("A" * 31 + "&long", "B" * 47 + "<long"),
    ("Café 日本語", "Crème & piñata"),
])
def test_svg_keeps_text_literal_and_truncates_before_escaping(title, subtitle):
    root = ET.fromstring(_placeholder_asset(1200, 1200, title, subtitle, ["#ffffff"]))
    texts = root.findall(f"{NS}text")
    assert [item.text for item in texts] == [title[:32], subtitle[:48]]
    assert all(len(item) == 0 for item in texts)


def test_palette_attributes_cannot_break_xml():
    palette = ['red" data-extra="x', "a&b", "<color>"]
    root = ET.fromstring(_placeholder_asset(1200, 1200, "Brand", "Product", palette))
    assert root.findall(f"{NS}rect")[0].attrib["fill"] == palette[0]
    assert root.findall(f"{NS}rect")[1].attrib["fill"] == palette[1]
    assert root.find(f"{NS}text").attrib["fill"] == palette[2]
    assert "data-extra" not in root.findall(f"{NS}rect")[0].attrib


def test_asset_and_photoshoot_outputs_are_parseable(tmp_path):
    profile = {"brand_name": "Fish & Chips <Co>", "tone_keywords": ["clear"], "color_palette": ["#ffffff"]}
    generate_asset_prompts(tmp_path, profile, {"angles": ["proof"]})
    generate_photoshoot_set(tmp_path, profile, "Cup & Saucer <Set>")
    files = sorted((tmp_path / "ad-assets").glob("*.svg"))
    assert len(files) == 9
    for path in files:
        root = ET.parse(path).getroot()
        title = root.find(f"{NS}text").text
        assert title == ("Cup & Saucer <Set>" if path.name.startswith("photoshoot-") else profile["brand_name"])
