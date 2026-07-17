#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from trial_tools import assignment_for, key_commitment


def main() -> int:
    parser = argparse.ArgumentParser(description="Assign one eligible PR within a concealed block of eight.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--eligible-index", required=True, type=int)
    parser.add_argument("--key-env", default="BUSLEYDEN_TRIAL_ASSIGNMENT_KEY")
    args = parser.parse_args()

    key = os.environ.get(args.key_env)
    if not key:
        parser.error(f"environment variable {args.key_env} is required")
    assignment = assignment_for(key, args.repository, args.eligible_index)
    print(json.dumps({
        "repository": args.repository.lower(),
        "eligible_index": args.eligible_index,
        "arm": assignment.arm,
        "block_index": assignment.block_index,
        "position_in_block": assignment.position_in_block,
        "assignment_digest": assignment.assignment_digest,
        "key_commitment": key_commitment(key),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
