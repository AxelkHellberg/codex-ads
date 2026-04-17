---
name: ads-generate
description: "Prompt and placeholder asset generator for paid-media image production inside Codex."
---

# Ads Generate

Use after `campaign-brief.md` exists.

1. Generate local prompts and placeholder assets:

```bash
python3 scripts/ads.py generate --brand-profile brand-profile.json --brief campaign-brief.md --output-dir .
```

2. If the user wants final creative files, use Codex image generation with the generated prompts and replace the placeholders.
