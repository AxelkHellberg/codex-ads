from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_ads.creative import (
    build_campaign_brief,
    extract_brand_dna,
    generate_asset_prompts,
    generate_photoshoot_set,
    write_brand_profile,
    write_campaign_brief,
)
from codex_ads.engine import (
    PLATFORM_CONFIG,
    build_generic_analysis,
    build_portfolio_audit,
    compute_ab_test,
    compute_math_model,
    load_json,
    write_analysis,
    write_audit_bundle,
    write_math_output,
    write_test_plan,
)
from codex_ads.reporting import build_pdf_report
from codex_ads.sync import sync_repo


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(prog="codex-ads")
    subparsers = command_parser.add_subparsers(dest="command", required=True)

    for name in ["audit", *PLATFORM_CONFIG.keys(), "creative", "landing", "budget", "plan", "competitor", "math", "test"]:
        sub = subparsers.add_parser(name)
        sub.add_argument("--input", dest="input_path")
        sub.add_argument("--output-dir", default=".")
        if name == "plan":
            sub.add_argument("--business-type", default=None)

    report = subparsers.add_parser("report")
    report.add_argument("--summary", required=True)
    report.add_argument("--output-dir", default=".")

    dna = subparsers.add_parser("dna")
    dna.add_argument("--url", required=True)
    dna.add_argument("--html-file")
    dna.add_argument("--output-dir", default=".")

    create = subparsers.add_parser("create")
    create.add_argument("--brand-profile", default="brand-profile.json")
    create.add_argument("--context")
    create.add_argument("--output-dir", default=".")

    generate = subparsers.add_parser("generate")
    generate.add_argument("--brand-profile", default="brand-profile.json")
    generate.add_argument("--brief", default="campaign-brief.md")
    generate.add_argument("--brief-json")
    generate.add_argument("--output-dir", default=".")

    photoshoot = subparsers.add_parser("photoshoot")
    photoshoot.add_argument("--brand-profile", default="brand-profile.json")
    photoshoot.add_argument("--product-name", default="Product")
    photoshoot.add_argument("--output-dir", default=".")

    sync = subparsers.add_parser("sync")
    sync.add_argument("--verify", action="store_true")
    sync.add_argument("--commit", action="store_true")
    sync.add_argument("--push", action="store_true")

    return command_parser


def _load_brand_profile(path: str) -> dict:
    return json.loads(Path(path).read_text())


def _load_brief(path: str) -> dict:
    text = Path(path).read_text()
    return {"angles": [line[2:] for line in text.splitlines() if line.startswith("- ")] or ["performance clarity"]}


def main() -> None:
    args = parser().parse_args()

    if args.command == "audit":
        summary = build_portfolio_audit(load_json(args.input_path))
        outputs = write_audit_bundle(args.output_dir, summary)
        print(json.dumps({key: str(value) for key, value in outputs.items()}, indent=2))
        return

    if args.command in PLATFORM_CONFIG:
        payload = load_json(args.input_path)
        platform_payload = payload.get("platforms", {}).get(args.command, payload)
        from codex_ads.engine import audit_platform

        result = audit_platform(args.command, platform_payload)
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        target = output / f"{args.command}-audit.json"
        target.write_text(json.dumps(result, indent=2) + "\n")
        print(target)
        return

    if args.command in {"creative", "landing", "budget", "competitor", "plan"}:
        payload = load_json(args.input_path)
        if args.command == "plan" and args.business_type:
            payload["business_type"] = args.business_type
        analysis = build_generic_analysis(args.command, payload)
        print(write_analysis(args.output_dir, analysis))
        return

    if args.command == "math":
        summary = compute_math_model(load_json(args.input_path))
        print(write_math_output(args.output_dir, summary))
        return

    if args.command == "test":
        summary = compute_ab_test(load_json(args.input_path))
        print(write_test_plan(args.output_dir, summary))
        return

    if args.command == "report":
        print(build_pdf_report(args.summary, args.output_dir))
        return

    if args.command == "dna":
        html_text = Path(args.html_file).read_text() if args.html_file else None
        profile = extract_brand_dna(args.url, html_text)
        print(write_brand_profile(args.output_dir, profile))
        return

    if args.command == "create":
        profile = _load_brand_profile(args.brand_profile)
        context = load_json(args.context) if args.context else {}
        brief = build_campaign_brief(profile, context)
        print(write_campaign_brief(args.output_dir, brief))
        return

    if args.command == "generate":
        profile = _load_brand_profile(args.brand_profile)
        brief = load_json(args.brief_json) if args.brief_json else _load_brief(args.brief)
        result = generate_asset_prompts(args.output_dir, profile, brief)
        print(json.dumps({key: str(value) for key, value in result.items()}, indent=2))
        return

    if args.command == "photoshoot":
        profile = _load_brand_profile(args.brand_profile)
        result = generate_photoshoot_set(args.output_dir, profile, args.product_name)
        print(json.dumps({key: str(value) for key, value in result.items()}, indent=2))
        return

    if args.command == "sync":
        print(json.dumps(sync_repo(Path.cwd(), verify=args.verify, commit=args.commit, push=args.push), indent=2))
        return


if __name__ == "__main__":
    main()
