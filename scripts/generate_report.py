#!/usr/bin/env python3

import argparse

from codex_ads.reporting import build_pdf_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    print(build_pdf_report(args.summary, args.output_dir))


if __name__ == "__main__":
    main()
