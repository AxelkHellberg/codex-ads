---
name: ads-photoshoot
description: "Product photoshoot prompt set for studio, floating, ingredient, in-use, and lifestyle treatments."
---

# Ads Photoshoot

Use when the user wants product-led visual variants.

```bash
python3 scripts/ads.py photoshoot --brand-profile brand-profile.json --product-name Product --output-dir .
```

Then use Codex image generation for final renders if the placeholders are not enough.
