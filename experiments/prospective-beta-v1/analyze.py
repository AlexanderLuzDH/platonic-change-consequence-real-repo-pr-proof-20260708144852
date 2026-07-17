#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trial_tools import analyze_records, format_analysis_markdown, load_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the preregistered prospective beta analysis.")
    parser.add_argument("records", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    records = load_records(args.records)
    analysis = analyze_records(records)
    json_text = json.dumps(analysis, indent=2, sort_keys=True) + "\n"
    markdown_text = format_analysis_markdown(analysis)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json_text, encoding="utf-8")
    else:
        print(json_text, end="")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
