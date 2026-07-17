#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trial_tools import validate_record


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate prospective beta trial records.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--skip-digest", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()

    files = [args.path] if args.path.is_file() else sorted(args.path.rglob("*.json"))
    files = [f for f in files if f.name not in {"PROTOCOL_MANIFEST.json", "ACTIVATION.json", "ACTIVATION.example.json"}]
    failures = 0
    results = []
    for file in files:
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
            errors = validate_record(payload, verify_digest=not args.skip_digest)
        except Exception as exc:
            errors = [str(exc)]
        failures += bool(errors)
        results.append({"file": str(file), "valid": not errors, "errors": errors})

    if args.json:
        print(json.dumps({"valid": failures == 0, "records": results}, indent=2, sort_keys=True))
    else:
        for result in results:
            print(f"{'PASS' if result['valid'] else 'FAIL'} {result['file']}")
            for error in result["errors"]:
                print(f"  - {error}")
        if not files:
            print(f"PASS {args.path}: no trial records yet")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
