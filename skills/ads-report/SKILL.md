---
name: ads-report
description: "Client-ready PDF reporting from the latest audit summary JSON."
---

# Ads Report

Use once `ads-audit-summary.json` exists and the user wants a packaged deliverable.

```bash
python3 scripts/generate_report.py --summary ads-audit-summary.json --output-dir .
```
