---
name: ads
description: "Codex-native paid media orchestrator for audits, planning, reporting, brand DNA extraction, and creative asset prompting."
argument-hint: "audit | google | meta | youtube | linkedin | tiktok | microsoft | apple | creative | landing | budget | plan | competitor | math | test | report | dna | create | generate | photoshoot"
license: MIT
---

# Ads

Use this skill as the public entrypoint for paid-media work in Codex.

## Intake

Start by collecting:

1. business type
2. monthly media budget
3. primary goal
4. active platforms
5. source material: exports, screenshots, pasted metrics, or landing page URLs

If the user already provided enough context, do not re-ask it.

## Command routing

- `audit`: portfolio review across active platforms
- `google`, `meta`, `youtube`, `linkedin`, `tiktok`, `microsoft`, `apple`: platform deep dives
- `creative`, `landing`, `budget`, `plan`, `competitor`: strategy and execution reviews
- `math`, `test`: deterministic calculation tools
- `report`: package the latest audit summary into a client-ready PDF
- `dna`, `create`, `generate`, `photoshoot`: creative pipeline from brand extraction through asset prompts

## Execution notes

- Prefer the deterministic CLI when a local artifact helps:
  `python3 scripts/ads.py <command> --input <file> --output-dir .`
- `audit` should write:
  - `ADS-AUDIT-REPORT.md`
  - `ADS-ACTION-PLAN.md`
  - `ADS-QUICK-WINS.md`
  - `ads-audit-summary.json`
- `report` should read `ads-audit-summary.json` and emit `ADS-REPORT.pdf`.
- For `generate` and `photoshoot`, first generate prompts/placeholders locally, then use Codex image generation when the user wants final raster assets.

## Output style

Lead with critical measurement and waste issues, then quick wins, then longer-term scaling advice.
