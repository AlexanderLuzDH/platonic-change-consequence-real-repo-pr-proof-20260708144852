#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trial_tools import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify frozen prospective-beta protocol files.")
    parser.add_argument("manifest", type=Path, nargs="?", default=Path(__file__).with_name("PROTOCOL_MANIFEST.json"))
    args = parser.parse_args()

    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.manifest.parents[2]
    failures = 0
    for item in payload["files"]:
        path = root / item["path"]
        actual = sha256_file(path) if path.is_file() else None
        valid = actual == item["sha256"]
        failures += not valid
        print(f"{'PASS' if valid else 'FAIL'} {item['path']} {actual or 'missing'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
