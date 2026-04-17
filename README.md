# Codex Ads

Codex Ads is a Codex-native plugin and local toolkit for paid-media audits, budget reviews, creative planning, client reporting, brand DNA extraction, asset prompt generation, and daily compatibility sync against a public upstream reference repository.

## What it ships

- Codex skills for `ads`, `ads-google`, `ads-meta`, `ads-youtube`, `ads-linkedin`, `ads-tiktok`, `ads-microsoft`, `ads-apple`, `ads-creative`, `ads-landing`, `ads-budget`, `ads-plan`, `ads-competitor`, `ads-math`, `ads-test`, `ads-report`, `ads-dna`, `ads-create`, `ads-generate`, and `ads-photoshoot`
- A Python CLI for deterministic local execution and automated verification
- Markdown, JSON, PDF, and placeholder asset outputs that match the paid-media workflow
- A daily upstream sync script that detects changes, regenerates derived metadata, verifies the repo, and can commit and push automatically

## Install

```bash
python3 -m pip install -e '.[dev]'
```

The plugin manifest lives at `.codex-plugin/plugin.json`. The runtime CLI is exposed as `codex-ads`.

## Command surface

```text
ads audit
ads google
ads meta
ads youtube
ads linkedin
ads tiktok
ads microsoft
ads apple
ads creative
ads landing
ads budget
ads plan
ads competitor
ads math
ads test
ads report
ads dna
ads create
ads generate
ads photoshoot
```

## Typical workflow

1. Provide a JSON payload or pasted metrics for one or more ad platforms.
2. Run `codex-ads audit --input <file>` to produce:
   - `ADS-AUDIT-REPORT.md`
   - `ADS-ACTION-PLAN.md`
   - `ADS-QUICK-WINS.md`
   - `ads-audit-summary.json`
3. Run `codex-ads report --summary ads-audit-summary.json` to generate `ADS-REPORT.pdf`.
4. Run `codex-ads dna --url https://example.com --html-file sample.html` or let Codex inspect the page directly.
5. Run `codex-ads create` and `codex-ads generate` to build briefs, asset prompts, and placeholder assets ready for Codex image generation.

## Example inputs

Sample fixtures for tests live in `tests/fixtures/`. The main audit schema is:

```json
{
  "business_type": "saas",
  "goal": "pipeline",
  "monthly_budget": 25000,
  "platforms": {
    "google": {
      "budget": 12000,
      "metrics": {
        "conversion_tracking_enabled": true,
        "enhanced_conversions_enabled": true,
        "wasted_spend_pct": 0.08
      }
    }
  }
}
```

## Daily sync

The repository includes:

- `sync/upstream-map.yaml`
- `sync/upstream-state.json`
- `scripts/sync_upstream.py`

Run it locally:

```bash
python3 scripts/sync_upstream.py --verify
```

To let it stage, commit, and push after verification:

```bash
python3 scripts/sync_upstream.py --verify --commit --push
```

Generated upstream inventories are written under `sync/generated/`.

## Verification

```bash
python3 -m pytest
```
