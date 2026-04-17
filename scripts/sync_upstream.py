#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from codex_ads.sync import sync_repo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    print(json.dumps(sync_repo(Path(__file__).resolve().parent.parent, verify=args.verify, commit=args.commit, push=args.push), indent=2))


if __name__ == "__main__":
    main()
