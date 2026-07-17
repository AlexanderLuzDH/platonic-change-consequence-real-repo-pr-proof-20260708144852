#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from trial_tools import audit_selection_for, key_commitment


def parse_bool(value: str) -> bool:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select a concealed primary audit before reviewer outcome.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--eligible-index", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--alerted", required=True, type=parse_bool)
    parser.add_argument("--key-env", default="BUSLEYDEN_TRIAL_AUDIT_KEY")
    args = parser.parse_args()

    key = os.environ.get(args.key_env)
    if not key:
        parser.error(f"environment variable {args.key_env} is required")
    selection = audit_selection_for(key, args.repository, args.eligible_index, args.head_sha, args.alerted)
    print(json.dumps({
        "repository": args.repository.lower(),
        "eligible_index": args.eligible_index,
        "head_sha": args.head_sha,
        "alerted": args.alerted,
        "primary_selected": selection.selected,
        "probability": selection.probability,
        "selection_digest": selection.selection_digest,
        "selection_score": selection.score,
        "key_commitment": key_commitment(key),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
