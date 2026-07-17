#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trial_tools import make_audit_packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a blinded stage-1 audit packet.")
    parser.add_argument("record", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    packet = make_audit_packet(record)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
