from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
GRADE_BANDS = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]


@dataclass
class Rule:
    rule_id: str
    title: str
    category: str
    severity: str
    metric: str
    evaluator: str
    target: Any
    warn: Any | None
    recommendation: str
    note: str


PLATFORM_CONFIG: dict[str, dict[str, Any]] = {
    "google": {
        "label": "Google Ads",
        "weights": {
            "conversion": 0.25,
            "waste": 0.20,
            "structure": 0.15,
            "keywords": 0.15,
            "ads": 0.15,
            "settings": 0.10,
        },
        "rules": [
            Rule("G01", "Conversion tracking is live", "conversion", "critical", "conversion_tracking_enabled", "bool_true", True, None, "Define a primary conversion action and validate the firing path.", "Missing tracking invalidates spend decisions."),
            Rule("G02", "Enhanced conversions are enabled", "conversion", "high", "enhanced_conversions_enabled", "bool_true", True, None, "Enable enhanced conversions for web or leads.", "This closes conversion gaps for modeled attribution."),
            Rule("G03", "Wasted spend stays below 15%", "waste", "critical", "wasted_spend_pct", "max", 0.05, 0.15, "Review search terms, negatives, and query intent filters.", "Paid search waste compounds quickly."),
            Rule("G04", "Brand and non-brand are separated", "structure", "high", "brand_nonbrand_split", "bool_true", True, None, "Split brand and non-brand into separate campaigns or portfolios.", "It is hard to tune bids otherwise."),
            Rule("G05", "Broad match is paired with smart bidding", "keywords", "critical", "broad_match_manual_cpc", "bool_false", False, None, "Move broad match traffic onto smart bidding or tighten match types.", "Broad match on manual CPC usually burns budget."),
            Rule("G06", "Search terms are reviewed every 14 days", "settings", "high", "search_term_review_days", "max", 7, 14, "Shorten the search term review cadence.", "Recent query drift matters."),
        ],
    },
    "meta": {
        "label": "Meta Ads",
        "weights": {"signal": 0.30, "creative": 0.30, "structure": 0.20, "audience": 0.20},
        "rules": [
            Rule("M01", "Pixel or CAPI is active", "signal", "critical", "pixel_or_capi_live", "bool_true", True, None, "Repair browser and server-side events before changing campaigns.", "Optimization quality depends on signal density."),
            Rule("M02", "EMQ stays above 6.0", "signal", "high", "emq_score", "min", 8.0, 6.0, "Increase event match parameters and server-side identifiers.", "Low EMQ reduces modeled lift."),
            Rule("M03", "Creative diversity is healthy", "creative", "high", "distinct_creatives", "min", 10, 6, "Add genuinely distinct hooks, formats, and offers.", "Meta benefits from fresh creative breadth."),
            Rule("M04", "Fatigue is under control", "creative", "medium", "fatigue_index", "max", 0.35, 0.55, "Rotate new concepts before the current set stalls.", "High fatigue drags CPM and CTR."),
            Rule("M05", "Learning-limited share stays low", "structure", "high", "learning_limited_pct", "max", 0.20, 0.35, "Consolidate fragmented ad sets and reduce premature edits.", "Too much fragmentation keeps delivery unstable."),
            Rule("M06", "Audience overlap stays below 25%", "audience", "medium", "audience_overlap_pct", "max", 0.15, 0.25, "Simplify overlapping ad sets and let broad targeting work.", "Overlap can inflate costs and muddle learning."),
        ],
    },
    "youtube": {
        "label": "YouTube Ads",
        "weights": {"creative": 0.35, "targeting": 0.20, "measurement": 0.25, "format": 0.20},
        "rules": [
            Rule("Y01", "Primary hook lands inside 5 seconds", "creative", "high", "hook_seconds", "max", 3, 5, "Recut the opening to land the promise earlier.", "Skippable formats punish slow openings."),
            Rule("Y02", "Channel includes multiple native formats", "format", "medium", "native_format_count", "min", 4, 2, "Build separate assets for Shorts, bumper, skippable, and Demand Gen.", "One format rarely carries the whole funnel."),
            Rule("Y03", "Video completion stays above 20%", "creative", "medium", "video_completion_rate", "min", 0.35, 0.20, "Trim length and tighten story progression.", "Completion signals weak resonance."),
            Rule("Y04", "Measurement is tied to video outcomes", "measurement", "high", "video_conversions_modeled", "bool_true", True, None, "Set engaged-view and site conversions before optimization.", "Video spend without measurement is hard to defend."),
            Rule("Y05", "CTV coverage is intentional", "targeting", "low", "ctv_enabled", "bool_true", True, None, "Review whether CTV inventory should be on or explicitly excluded.", "Connected TV often changes CPM mix."),
        ],
    },
    "linkedin": {
        "label": "LinkedIn Ads",
        "weights": {"signal": 0.25, "audience": 0.25, "creative": 0.20, "leadgen": 0.15, "budget": 0.15},
        "rules": [
            Rule("L01", "Insight Tag is live", "signal", "critical", "insight_tag_live", "bool_true", True, None, "Fix the tag before expanding spend.", "LinkedIn optimization is weak without durable signals."),
            Rule("L02", "Audience size stays above 50k", "audience", "medium", "audience_size", "min", 150000, 50000, "Broaden targeting or stack exclusions differently.", "Tiny audiences spike CPM."),
            Rule("L03", "Lead-gen form completion rate is healthy", "leadgen", "high", "form_completion_rate", "min", 0.20, 0.10, "Shorten the form and move lower-value questions downstream.", "Friction compounds on LinkedIn."),
            Rule("L04", "Creative variants cover multiple angles", "creative", "medium", "creative_angles", "min", 4, 2, "Build more variants by persona, pain, and proof type.", "B2B creatives need more than one angle."),
            Rule("L05", "Budget is not trapped in testing", "budget", "medium", "campaigns_under_min_budget_pct", "max", 0.20, 0.40, "Concentrate spend into fewer ad groups or campaigns.", "Too many low-budget campaigns never exit learning."),
        ],
    },
    "tiktok": {
        "label": "TikTok Ads",
        "weights": {"creative": 0.30, "signal": 0.25, "bidding": 0.20, "structure": 0.15, "performance": 0.10},
        "rules": [
            Rule("T01", "Creative is native to TikTok", "creative", "critical", "native_tiktok_ratio", "min", 0.80, 0.50, "Replace over-produced cuts with native-feeling hooks and pacing.", "TikTok punishes generic repurposed creative."),
            Rule("T02", "Sound-on readiness is present", "creative", "high", "sound_on_ready", "bool_true", True, None, "Add spoken hooks, captions, and music-aware edits.", "Silent assets underperform on TikTok."),
            Rule("T03", "Events API or pixel is live", "signal", "critical", "events_api_live", "bool_true", True, None, "Stabilize signal collection before scale decisions.", "Signal quality drives Smart+ outcomes."),
            Rule("T04", "Budget can clear the learning bar", "bidding", "high", "daily_budget_vs_cpa_multiple", "min", 50, 20, "Raise budget or narrow testing scope.", "TikTok needs enough spend to learn."),
            Rule("T05", "Safe-zone compliance is clean", "structure", "medium", "safe_zone_violations", "max", 0, 2, "Reframe text and product shots away from UI overlays.", "Bad framing hurts readability."),
        ],
    },
    "microsoft": {
        "label": "Microsoft Ads",
        "weights": {"signal": 0.25, "syndication": 0.20, "structure": 0.20, "creative": 0.20, "settings": 0.15},
        "rules": [
            Rule("B01", "UET tracking is live", "signal", "critical", "uet_live", "bool_true", True, None, "Repair UET before scaling or importing more campaigns.", "Microsoft optimization depends on UET integrity."),
            Rule("B02", "Google import is reviewed recently", "structure", "medium", "google_import_review_days", "max", 7, 21, "Validate the imported settings and unsupported fields.", "Imports drift over time."),
            Rule("B03", "Audience network is intentional", "settings", "medium", "audience_network_opted_in", "bool_true", True, None, "Audit whether audience network placement matches the goal.", "Default inventory mix can mask performance."),
            Rule("B04", "Search partners are monitored", "syndication", "medium", "partner_performance_review_days", "max", 14, 30, "Break out search partners and trim weak syndication pockets.", "Partner traffic quality can vary widely."),
            Rule("B05", "Responsive assets are complete", "creative", "high", "rsa_asset_coverage_pct", "min", 0.90, 0.70, "Complete headlines, descriptions, and image extensions.", "Sparse assets cap impression quality."),
        ],
    },
    "apple": {
        "label": "Apple Ads",
        "weights": {"structure": 0.25, "creative": 0.20, "signal": 0.20, "bids": 0.20, "coverage": 0.15},
        "rules": [
            Rule("A01", "Campaigns are split by intent", "structure", "high", "intent_split", "bool_true", True, None, "Separate branded, category, competitor, and discovery intents.", "Intent mixing distorts bid control."),
            Rule("A02", "CPP coverage is broad enough", "creative", "medium", "cpp_coverage_pct", "min", 0.70, 0.40, "Create more Custom Product Pages mapped to major audiences.", "Low CPP coverage weakens message match."),
            Rule("A03", "AdAttributionKit or MMP is validated", "signal", "critical", "attribution_verified", "bool_true", True, None, "Verify attribution stack before scaling bids.", "Mobile spend without verified attribution is risky."),
            Rule("A04", "Search match is constrained", "bids", "medium", "search_match_broad_pct", "max", 0.15, 0.30, "Tighten discovery and protect exact intent buckets.", "Too much search match can dilute spend."),
            Rule("A05", "Placement coverage is deliberate", "coverage", "low", "tap_coverage_count", "min", 3, 2, "Review Search, Today, and Product Pages placements.", "Coverage should reflect the funnel plan."),
        ],
    },
}


def grade_for(score: float) -> str:
    for threshold, grade in GRADE_BANDS:
        if score >= threshold:
            return grade
    return "F"


def _evaluate(rule: Rule, value: Any) -> tuple[str, float, str]:
    if value is None:
        return "warning", 45.0, "Metric missing. Supply account data for a sharper assessment."

    if rule.evaluator == "bool_true":
        status = "pass" if bool(value) else "fail"
        score = 100.0 if status == "pass" else 10.0
    elif rule.evaluator == "bool_false":
        status = "pass" if not bool(value) else "fail"
        score = 100.0 if status == "pass" else 10.0
    elif rule.evaluator == "max":
        if value <= rule.target:
            status, score = "pass", 100.0
        elif rule.warn is not None and value <= rule.warn:
            status, score = "warning", 60.0
        else:
            status, score = "fail", 20.0
    elif rule.evaluator == "min":
        if value >= rule.target:
            status, score = "pass", 100.0
        elif rule.warn is not None and value >= rule.warn:
            status, score = "warning", 60.0
        else:
            status, score = "fail", 20.0
    else:
        raise ValueError(f"Unsupported evaluator: {rule.evaluator}")
    evidence = f"{rule.metric}={value}"
    return status, score, evidence


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        if 0 <= value <= 1:
            return f"{value:.0%}"
        return f"{value:.2f}"
    return str(value)


def audit_platform(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    config = PLATFORM_CONFIG[name]
    metrics = payload.get("metrics", {})
    category_scores: dict[str, list[float]] = {key: [] for key in config["weights"]}
    findings = []

    for rule in config["rules"]:
        value = metrics.get(rule.metric)
        status, score, evidence = _evaluate(rule, value)
        category_scores[rule.category].append(score)
        findings.append(
            {
                "id": rule.rule_id,
                "title": rule.title,
                "category": rule.category,
                "severity": rule.severity,
                "status": status,
                "score": score,
                "metric": rule.metric,
                "value": _format_metric(value) if value is not None else "missing",
                "evidence": evidence,
                "note": rule.note,
                "recommendation": rule.recommendation,
            }
        )

    weighted = 0.0
    category_breakdown = {}
    for category, weight in config["weights"].items():
        values = category_scores.get(category) or [50.0]
        avg = sum(values) / len(values)
        weighted += avg * weight
        category_breakdown[category] = round(avg, 1)

    findings.sort(
        key=lambda item: (
            0 if item["status"] == "fail" else 1 if item["status"] == "warning" else 2,
            -SEVERITY_ORDER[item["severity"]],
            item["id"],
        )
    )

    quick_wins = [
        finding
        for finding in findings
        if finding["status"] != "pass" and finding["severity"] in {"critical", "high"}
    ][:5]

    return {
        "platform": name,
        "label": config["label"],
        "budget": payload.get("budget", 0),
        "score": round(weighted, 1),
        "grade": grade_for(weighted),
        "category_breakdown": category_breakdown,
        "findings": findings,
        "quick_wins": quick_wins,
    }


def build_portfolio_audit(payload: dict[str, Any]) -> dict[str, Any]:
    platforms = payload.get("platforms", {})
    results = []
    total_budget = 0.0
    for name in PLATFORM_CONFIG:
        if name in platforms:
            platform_payload = dict(platforms[name])
            platform_payload.setdefault("budget", 0)
            total_budget += float(platform_payload["budget"])
            results.append(audit_platform(name, platform_payload))

    if not results:
        return {
            "business_type": payload.get("business_type", "unknown"),
            "goal": payload.get("goal", "unknown"),
            "monthly_budget": payload.get("monthly_budget", 0),
            "score": 0,
            "grade": "F",
            "platforms": [],
            "top_issues": [],
            "quick_wins": [],
            "notes": ["No platform payloads were supplied. Provide metrics or exports before auditing."],
        }

    aggregate = 0.0
    top_issues = []
    quick_wins = []
    for result in results:
        share = (result["budget"] / total_budget) if total_budget else (1 / len(results))
        result["budget_share"] = round(share, 4)
        aggregate += result["score"] * share
        top_issues.extend(item for item in result["findings"] if item["status"] == "fail")
        quick_wins.extend(result["quick_wins"])

    top_issues.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["id"]))
    quick_wins.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["id"]))
    score = round(aggregate, 1)
    return {
        "business_type": payload.get("business_type", "unknown"),
        "goal": payload.get("goal", "unknown"),
        "monthly_budget": payload.get("monthly_budget", total_budget),
        "score": score,
        "grade": grade_for(score),
        "platforms": results,
        "top_issues": top_issues[:8],
        "quick_wins": quick_wins[:8],
        "notes": [
            "Interpret scores relative to business model, budget, and signal quality.",
            "Apply fixes in priority order: measurement first, then waste, then scaling.",
        ],
    }


def _markdown_table(rows: list[tuple[str, str, str, str]]) -> str:
    lines = ["| ID | Severity | Status | Recommendation |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")
    return "\n".join(lines)


def write_audit_bundle(output_dir: str | Path, summary: dict[str, Any]) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / "ADS-AUDIT-REPORT.md"
    action_path = output_path / "ADS-ACTION-PLAN.md"
    quick_path = output_path / "ADS-QUICK-WINS.md"
    json_path = output_path / "ads-audit-summary.json"

    report_lines = [
        f"# Ads Audit Report",
        "",
        f"- Business type: `{summary['business_type']}`",
        f"- Goal: `{summary['goal']}`",
        f"- Monthly budget: `${summary['monthly_budget']}`",
        f"- Ads Health Score: `{summary['score']}` ({summary['grade']})",
        "",
        "## Executive Summary",
        "",
    ]
    if summary["platforms"]:
        for platform in summary["platforms"]:
            report_lines.extend(
                [
                    f"### {platform['label']}",
                    f"- Score: `{platform['score']}` ({platform['grade']})",
                    f"- Budget share: `{platform.get('budget_share', 0):.0%}`",
                    f"- Category breakdown: `{json.dumps(platform['category_breakdown'], sort_keys=True)}`",
                    "",
                ]
            )
            rows = [
                (
                    finding["id"],
                    finding["severity"],
                    finding["status"],
                    finding["recommendation"],
                )
                for finding in platform["findings"][:6]
            ]
            report_lines.append(_markdown_table(rows))
            report_lines.append("")
    else:
        report_lines.extend(f"- {note}" for note in summary["notes"])
        report_lines.append("")

    action_lines = [
        "# Ads Action Plan",
        "",
        "## Priority queue",
        "",
    ]
    for finding in summary["top_issues"]:
        action_lines.extend(
            [
                f"### {finding['id']} - {finding['title']}",
                f"- Severity: `{finding['severity']}`",
                f"- Why it matters: {finding['note']}",
                f"- Next action: {finding['recommendation']}",
                "",
            ]
        )
    if not summary["top_issues"]:
        action_lines.append("- No blocking issues were detected from the supplied payload.")
        action_lines.append("")

    quick_lines = [
        "# Ads Quick Wins",
        "",
        "These items are the fastest high-impact fixes surfaced by the current payload.",
        "",
    ]
    for finding in summary["quick_wins"]:
        quick_lines.append(f"- `{finding['id']}`: {finding['recommendation']}")
    if not summary["quick_wins"]:
        quick_lines.append("- No quick wins available without more platform data.")

    report_path.write_text("\n".join(report_lines).strip() + "\n")
    action_path.write_text("\n".join(action_lines).strip() + "\n")
    quick_path.write_text("\n".join(quick_lines).strip() + "\n")
    json_path.write_text(json.dumps(summary, indent=2) + "\n")
    return {
        "report": report_path,
        "action_plan": action_path,
        "quick_wins": quick_path,
        "summary": json_path,
    }


def build_generic_analysis(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    builders = {
        "creative": _build_creative_analysis,
        "landing": _build_landing_analysis,
        "budget": _build_budget_analysis,
        "competitor": _build_competitor_analysis,
        "plan": _build_plan_analysis,
    }
    return builders[kind](payload)


def _status_for(score: float) -> str:
    if score >= 85:
        return "strong"
    if score >= 65:
        return "watch"
    return "weak"


def _build_creative_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics", {})
    scores = {
        "variety": min(100, int(metrics.get("creative_angles", 3) * 20)),
        "fatigue": max(0, 100 - int(metrics.get("fatigue_index", 0.4) * 100)),
        "native_fit": int(metrics.get("native_format_coverage", 0.7) * 100),
        "video_mix": int(metrics.get("video_asset_share", 0.5) * 100),
    }
    average = round(sum(scores.values()) / len(scores), 1)
    priorities = [
        "Refresh hooks and proof points when fatigue rises above 0.55.",
        "Maintain at least three visual systems per platform to avoid concept collapse.",
        "Review message match between creative promise and landing page lead."
    ]
    return {
        "title": "Creative Audit",
        "score": average,
        "status": _status_for(average),
        "metrics": scores,
        "priorities": priorities,
        "filename": "ADS-CREATIVE-AUDIT.md",
    }


def _build_landing_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics", {})
    scores = {
        "message_match": int(metrics.get("message_match_score", 0.7) * 100),
        "speed": max(0, 100 - int(metrics.get("mobile_lcp_seconds", 3.5) * 12)),
        "form_friction": max(0, 100 - int(metrics.get("form_fields", 6) * 10)),
        "trust": min(100, int(metrics.get("trust_signal_count", 5) * 12)),
    }
    average = round(sum(scores.values()) / len(scores), 1)
    priorities = [
        "Match hero promise and CTA language to the ad promise.",
        "Keep the first interactive element above the fold on mobile.",
        "Reduce form fields unless the lead qualification step is proven."
    ]
    return {
        "title": "Landing Page Review",
        "score": average,
        "status": _status_for(average),
        "metrics": scores,
        "priorities": priorities,
        "filename": "ADS-LANDING-AUDIT.md",
    }


def _build_budget_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    spend = payload.get("spend", {})
    total = sum(spend.values()) or 1
    recommendations = []
    for platform, amount in sorted(spend.items()):
        share = amount / total
        if share > 0.6:
            recommendations.append(f"Reduce concentration risk on {platform} or justify why it earns {share:.0%} of budget.")
        elif share < 0.1:
            recommendations.append(f"Decide whether {platform} deserves more budget or should be paused as noise.")
    if not recommendations:
        recommendations.append("Current allocation looks balanced across the supplied channels.")
    return {
        "title": "Budget Review",
        "score": round(100 - (len(recommendations) - 1) * 8, 1),
        "status": "watch" if recommendations else "strong",
        "metrics": {platform: round(amount / total * 100, 1) for platform, amount in spend.items()},
        "priorities": recommendations,
        "filename": "ADS-BUDGET-REVIEW.md",
    }


def _build_competitor_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    competitors = payload.get("competitors", [])
    gap_count = sum(len(item.get("gaps", [])) for item in competitors)
    opp_count = sum(len(item.get("opportunities", [])) for item in competitors)
    score = max(40, min(95, 60 + opp_count * 5 - gap_count * 2))
    priorities = []
    for item in competitors:
        if item.get("gaps"):
            priorities.append(f"{item['name']}: close gaps in {', '.join(item['gaps'])}.")
        if item.get("opportunities"):
            priorities.append(f"{item['name']}: exploit whitespace in {', '.join(item['opportunities'])}.")
    if not priorities:
        priorities.append("Capture competitor messaging, offers, and placements before making a recommendation.")
    return {
        "title": "Competitor Review",
        "score": score,
        "status": _status_for(score),
        "metrics": {"competitors_reviewed": len(competitors), "opportunities": opp_count, "gaps": gap_count},
        "priorities": priorities,
        "filename": "ADS-COMPETITOR.md",
    }


def _build_plan_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    business_type = payload.get("business_type", "saas")
    phase_map = {
        "saas": ["Search + demand capture", "Paid social proofing", "Video retargeting"],
        "ecommerce": ["Search + shopping", "Meta prospecting", "Retention and creator scale"],
        "local-service": ["Search + calls", "LSA or local trust layer", "Retargeting and referral loops"],
        "b2b-enterprise": ["LinkedIn demand capture", "Search intent coverage", "ABM retargeting"],
    }
    phases = phase_map.get(business_type, ["Intent capture", "Creative scale", "Retention and expansion"])
    return {
        "title": f"Media Plan for {business_type}",
        "score": 88.0,
        "status": "strong",
        "metrics": {"phases": len(phases), "business_type": business_type},
        "priorities": [f"Phase {index + 1}: {phase}" for index, phase in enumerate(phases)],
        "filename": "ADS-PLAN.md",
    }


def write_analysis(output_dir: str | Path, analysis: dict[str, Any]) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / analysis["filename"]
    lines = [
        f"# {analysis['title']}",
        "",
        f"- Score: `{analysis['score']}`",
        f"- Status: `{analysis['status']}`",
        "",
        "## Metrics",
        "",
    ]
    for key, value in analysis["metrics"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Priorities", ""])
    lines.extend(f"- {item}" for item in analysis["priorities"])
    target.write_text("\n".join(lines).strip() + "\n")
    return target


def compute_math_model(payload: dict[str, Any]) -> dict[str, Any]:
    spend = float(payload.get("spend", 0))
    clicks = float(payload.get("clicks", 0))
    conversions = float(payload.get("conversions", 0))
    revenue = float(payload.get("revenue", 0))
    gross_margin = float(payload.get("gross_margin", 0.7))
    ltv = float(payload.get("ltv", 0))

    cpc = spend / clicks if clicks else 0
    cpa = spend / conversions if conversions else math.inf
    roas = revenue / spend if spend else 0
    break_even_cpa = (revenue * gross_margin / conversions) if conversions else 0
    ltv_cac = (ltv / cpa) if conversions and cpa not in {0, math.inf} else 0

    return {
        "spend": spend,
        "clicks": clicks,
        "conversions": conversions,
        "revenue": revenue,
        "cpc": round(cpc, 2),
        "cpa": None if cpa is math.inf else round(cpa, 2),
        "roas": round(roas, 2),
        "break_even_cpa": round(break_even_cpa, 2),
        "ltv_cac": round(ltv_cac, 2),
    }


def write_math_output(output_dir: str | Path, summary: dict[str, Any]) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / "ADS-MATH.md"
    lines = ["# PPC Math", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    target.write_text("\n".join(lines) + "\n")
    return target


def compute_ab_test(payload: dict[str, Any]) -> dict[str, Any]:
    baseline_rate = float(payload.get("baseline_rate", 0.03))
    minimum_detectable_effect = float(payload.get("minimum_detectable_effect", 0.15))
    weekly_visitors = int(payload.get("weekly_visitors", 10000))
    sample_per_variant = max(1000, int((16 * baseline_rate * (1 - baseline_rate)) / (baseline_rate * minimum_detectable_effect) ** 2))
    weeks = max(1, math.ceil((sample_per_variant * 2) / weekly_visitors))
    return {
        "baseline_rate": baseline_rate,
        "minimum_detectable_effect": minimum_detectable_effect,
        "sample_per_variant": sample_per_variant,
        "estimated_duration_weeks": weeks,
        "recommendation": "Hold the winner only after the full duration unless a guardrail metric breaks.",
    }


def write_test_plan(output_dir: str | Path, plan: dict[str, Any]) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    target = output_path / "ADS-TEST-PLAN.md"
    lines = ["# Paid Media Experiment Plan", ""]
    for key, value in plan.items():
        lines.append(f"- {key}: `{value}`")
    target.write_text("\n".join(lines) + "\n")
    return target


def load_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(Path(path).read_text())
