from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _validate_summary(summary: object) -> None:
    if not isinstance(summary, dict):
        raise ValueError("summary must be a JSON object")
    platforms = summary.get("platforms", [])
    if not isinstance(platforms, list):
        raise ValueError("summary.platforms must be a list")
    for platform_index, platform in enumerate(platforms):
        path = f"summary.platforms[{platform_index}]"
        if not isinstance(platform, dict):
            raise ValueError(f"{path} must be a JSON object")
        for field in ("label", "score", "grade"):
            if field not in platform:
                raise ValueError(f"{path}.{field} is required")
        findings = platform.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError(f"{path}.findings must be a list")
        for finding_index, finding in enumerate(findings):
            finding_path = f"{path}.findings[{finding_index}]"
            if not isinstance(finding, dict):
                raise ValueError(f"{finding_path} must be a JSON object")
            for field in ("id", "severity", "title", "recommendation"):
                if field not in finding:
                    raise ValueError(f"{finding_path}.{field} is required")


def build_pdf_report(summary_path: str | Path, output_dir: str | Path) -> Path:
    summary = json.loads(Path(summary_path).read_text())
    _validate_summary(summary)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / "ADS-REPORT.pdf"

    styles = getSampleStyleSheet()
    story = [
        Paragraph("Codex Ads Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(escape(f"Business type: {summary.get('business_type', 'unknown')}"), styles["BodyText"]),
        Paragraph(escape(f"Goal: {summary.get('goal', 'unknown')}"), styles["BodyText"]),
        Paragraph(escape(f"Health score: {summary.get('score', 0)} ({summary.get('grade', 'F')})"), styles["BodyText"]),
        Spacer(1, 12),
    ]

    for platform in summary.get("platforms", []):
        story.extend(
            [
                Paragraph(escape(str(platform["label"])), styles["Heading2"]),
                Paragraph(escape(f"Score: {platform['score']} ({platform['grade']})"), styles["BodyText"]),
            ]
        )
        for finding in platform.get("findings", [])[:5]:
            story.append(
                Paragraph(
                    escape(f"{finding['id']} [{finding['severity']}] {finding['title']}: {finding['recommendation']}"),
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 10))

    document = SimpleDocTemplate(str(target), pagesize=LETTER, title="Codex Ads Report")
    document.build(story)
    return target
