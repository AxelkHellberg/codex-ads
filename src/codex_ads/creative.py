from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "codex-ads/0.1"})
    with urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8", errors="ignore")


def extract_brand_dna(url: str, html_text: str | None = None) -> dict:
    html = html_text if html_text is not None else _fetch_html(url)
    colors = sorted(set(match.lower() for match in re.findall(r"#[0-9a-fA-F]{6}", html)))[:8]
    title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    description_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        re.I | re.S,
    )
    headings = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.I | re.S)
    text_blob = re.sub(r"<[^>]+>", " ", html)
    words = re.findall(r"[A-Za-z]{4,}", text_blob.lower())
    strong_words = sorted(set(word for word in words if word in {"premium", "trusted", "fast", "growth", "clarity", "performance", "simple", "smart"}))
    host = urlparse(url).netloc or url

    return {
        "source_url": url,
        "brand_name": title_match.group(1).strip() if title_match else host,
        "description": description_match.group(1).strip() if description_match else "",
        "color_palette": colors or ["#0b6e4f", "#1f2937", "#f4f6f8"],
        "headline_themes": [re.sub(r"\s+", " ", item).strip() for item in headings[:6]],
        "tone_keywords": strong_words or ["clear", "credible", "performance"],
        "visual_direction": [
            "use clean hierarchy and proof-first layouts",
            "prefer product-led close crops or interface-led moments",
            "keep messaging punchy and easy to scan on paid placements",
        ],
    }


def write_brand_profile(output_dir: str | Path, profile: dict) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / "brand-profile.json"
    target.write_text(json.dumps(profile, indent=2) + "\n")
    return target


def build_campaign_brief(profile: dict, context: dict | None = None) -> dict:
    context = context or {}
    tone = ", ".join(profile.get("tone_keywords", [])[:3])
    phases = context.get("phases") or ["acquisition", "retargeting", "expansion"]
    concepts = []
    for phase in phases:
        concepts.append(
            {
                "phase": phase,
                "headline": f"{profile['brand_name']} for {phase}",
                "hook": f"{profile['brand_name']} delivers {tone} outcomes without wasting budget.",
                "cta": "Start now",
            }
        )
    return {
        "brand_name": profile["brand_name"],
        "positioning": profile.get("description", ""),
        "tone_keywords": profile.get("tone_keywords", []),
        "angles": profile.get("headline_themes", [])[:4] or ["proof", "clarity", "speed"],
        "concepts": concepts,
        "platform_matrix": {
            "google": "intent capture and direct-response hooks",
            "meta": "visual proof and social resonance",
            "linkedin": "persona-specific pain and ROI proof",
            "tiktok": "native demos and fast hook testing",
        },
    }


def write_campaign_brief(output_dir: str | Path, brief: dict) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / "campaign-brief.md"
    lines = [
        f"# Campaign Brief: {brief['brand_name']}",
        "",
        f"- Positioning: {brief['positioning']}",
        f"- Tone: {', '.join(brief['tone_keywords'])}",
        "",
        "## Angles",
        "",
    ]
    lines.extend(f"- {angle}" for angle in brief["angles"])
    lines.extend(["", "## Concepts", ""])
    for concept in brief["concepts"]:
        lines.extend(
            [
                f"### {concept['phase'].title()}",
                f"- Headline: {concept['headline']}",
                f"- Hook: {concept['hook']}",
                f"- CTA: {concept['cta']}",
                "",
            ]
        )
    lines.extend(["## Platform Matrix", ""])
    for platform, note in brief["platform_matrix"].items():
        lines.append(f"- {platform}: {note}")
    target.write_text("\n".join(lines).strip() + "\n")
    return target


SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="{bg}"/>
<rect x="24" y="24" width="{inner_w}" height="{inner_h}" rx="8" fill="{card}"/>
<text x="48" y="88" fill="{fg}" font-family="Arial" font-size="34">{title}</text>
<text x="48" y="136" fill="{fg}" font-family="Arial" font-size="22">{subtitle}</text>
</svg>
"""


def _placeholder_asset(width: int, height: int, title: str, subtitle: str, palette: list[str]) -> str:
    bg = palette[0]
    card = palette[1] if len(palette) > 1 else "#1f2937"
    fg = palette[2] if len(palette) > 2 else "#f4f6f8"
    return SVG_TEMPLATE.format(
        width=width,
        height=height,
        inner_w=max(width - 48, 20),
        inner_h=max(height - 48, 20),
        bg=bg,
        card=card,
        fg=fg,
        title=title[:32],
        subtitle=subtitle[:48],
    )


def generate_asset_prompts(output_dir: str | Path, profile: dict, brief: dict, placeholder: bool = True) -> dict:
    asset_dir = Path(output_dir) / "ad-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    specs = {
        "google-square": (1200, 1200),
        "meta-reel": (1080, 1920),
        "linkedin-feed": (1200, 1200),
        "tiktok-video-cover": (1080, 1920),
    }
    manifest = {"brand": profile["brand_name"], "assets": []}
    for name, dims in specs.items():
        prompt = f"Create a paid media asset for {profile['brand_name']} with tone {', '.join(profile['tone_keywords'])} and angle {brief['angles'][0]}."
        record = {"name": name, "width": dims[0], "height": dims[1], "prompt": prompt}
        if placeholder:
            asset_path = asset_dir / f"{name}.svg"
            asset_path.write_text(_placeholder_asset(dims[0], dims[1], profile["brand_name"], name, profile["color_palette"]))
            record["placeholder_path"] = str(asset_path.name)
        manifest["assets"].append(record)

    manifest_path = asset_dir / "asset-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    prompts_path = asset_dir / "asset-prompts.md"
    prompt_lines = [f"# Asset Prompts for {profile['brand_name']}", ""]
    for record in manifest["assets"]:
        prompt_lines.extend([f"## {record['name']}", "", record["prompt"], ""])
    prompts_path.write_text("\n".join(prompt_lines).strip() + "\n")
    return {"manifest": manifest_path, "prompts": prompts_path, "asset_dir": asset_dir}


def generate_photoshoot_set(output_dir: str | Path, profile: dict, product_name: str = "Product") -> dict:
    asset_dir = Path(output_dir) / "ad-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    styles = ["studio", "floating", "ingredient", "in-use", "lifestyle"]
    prompts = []
    for style in styles:
        prompt = f"Photograph {product_name} in a {style} setup for {profile['brand_name']} using {', '.join(profile['tone_keywords'])} direction."
        file_path = asset_dir / f"photoshoot-{style}.svg"
        file_path.write_text(_placeholder_asset(1200, 1200, product_name, style, profile["color_palette"]))
        prompts.append({"style": style, "prompt": prompt, "placeholder_path": file_path.name})
    prompt_path = asset_dir / "photoshoot-prompts.json"
    prompt_path.write_text(json.dumps({"product_name": product_name, "styles": prompts}, indent=2) + "\n")
    return {"manifest": prompt_path, "asset_dir": asset_dir}
