from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_pdf_report(summary_path: str | Path, output_dir: str | Path) -> Path:
    summary = json.loads(Path(summary_path).read_text())
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / "ADS-REPORT.pdf"

    styles = getSampleStyleSheet()
    story = [
        Paragraph("Codex Ads Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Business type: {summary.get('business_type', 'unknown')}", styles["BodyText"]),
        Paragraph(f"Goal: {summary.get('goal', 'unknown')}", styles["BodyText"]),
        Paragraph(f"Health score: {summary.get('score', 0)} ({summary.get('grade', 'F')})", styles["BodyText"]),
        Spacer(1, 12),
    ]

    for platform in summary.get("platforms", []):
        story.extend(
            [
                Paragraph(platform["label"], styles["Heading2"]),
                Paragraph(f"Score: {platform['score']} ({platform['grade']})", styles["BodyText"]),
            ]
        )
        for finding in platform.get("findings", [])[:5]:
            story.append(
                Paragraph(
                    f"{finding['id']} [{finding['severity']}] {finding['title']}: {finding['recommendation']}",
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 10))

    document = SimpleDocTemplate(str(target), pagesize=LETTER, title="Codex Ads Report")
    document.build(story)
    return target
