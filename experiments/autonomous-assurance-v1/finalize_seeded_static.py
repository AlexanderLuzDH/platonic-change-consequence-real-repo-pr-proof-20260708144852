#!/usr/bin/env python3
"""Finalize the 500-case audit from an immutable 495-case seed plus HTTPie.

This avoids re-querying hundreds of unchanged upstream commits. The seed names
its preserved Actions artifact and digest. Only projects absent from the seed
are fetched, classified, and added to the final aggregate.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import run_corrected_static as corrected

base = corrected.base
FIELDS = [
    "relevant_test_added",
    "relevant_test_modified",
    "relevant_test_changed",
    "relevant_test_unchanged_proxy",
    "any_test_changed",
    "unrelated_test_change_only",
    "same_stem_discoverable",
    "candidate_path_discoverable",
]
REPO_ALIASES = {"jakubroztocil/httpie": "httpie/cli"}


def bugsinpy_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def project_counts(records):
    result = {}
    for record in records:
        row = result.setdefault(record.project, {"total": 0, **{field: 0 for field in FIELDS}})
        row["total"] += 1
        for field in FIELDS:
            row[field] += int(bool(getattr(record, field)))
    return result


def wilson(successes: int, total: int, z: float = 1.6448536269514722):
    if not total:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def cluster_interval(counts: dict, field: str, seed: int = 61062, reps: int = 5000):
    projects = sorted(counts)
    if not projects:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(reps):
        selected = [rng.choice(projects) for _ in projects]
        total = sum(counts[project]["total"] for project in selected)
        successes = sum(counts[project][field] for project in selected)
        values.append(successes / total)
    values.sort()
    return [values[int(0.05 * (reps - 1))], values[int(0.95 * (reps - 1))]]


def rate(counts: dict, field: str):
    total = sum(row["total"] for row in counts.values())
    successes = sum(row[field] for row in counts.values())
    return {
        "successes": successes,
        "total": total,
        "rate": successes / total if total else None,
        "wilson90": wilson(successes, total),
        "project_cluster_bootstrap90": cluster_interval(counts, field),
    }


def merge_counts(seed_counts: dict, new_counts: dict):
    merged = json.loads(json.dumps(seed_counts))
    overlap = set(merged) & set(new_counts)
    if overlap:
        raise ValueError(f"seed/new project overlap: {sorted(overlap)}")
    merged.update(new_counts)
    return merged


def summarize(seed: dict, records, metadata_cases: int):
    good = [record for record in records if record.commit_api_status == "ok"]
    counts = merge_counts(seed["project_counts"], project_counts(good))
    evidence = {
        field: rate(counts, field)
        for field in [
            "relevant_test_added",
            "relevant_test_modified",
            "relevant_test_changed",
            "relevant_test_unchanged_proxy",
            "any_test_changed",
            "unrelated_test_change_only",
        ]
    }
    mapping = {
        field: rate(counts, field)
        for field in ["same_stem_discoverable", "candidate_path_discoverable"]
    }
    total = sum(row["total"] for row in counts.values())
    unchanged = evidence["relevant_test_unchanged_proxy"]["successes"]
    no_test_change = total - evidence["any_test_changed"]["successes"]
    return {
        "schema_version": 3,
        "kind": "autonomous_assurance_seeded_500_case_audit",
        "claim_boundary": (
            "Original upstream fixed-commit file statuses plus BugsInPy-selected tests. "
            "Historical evidence-state proxies, not complete logical sufficiency or human usefulness."
        ),
        "instrument_history": [
            "Pilot patch-only test-state proxy rejected because BugsInPy strips tests from bug_patch.txt.",
            "Upstream-commit audit preserved as a 495-case artifact.",
            "Final audit adds five previously omitted HTTPie cases by fetching only missing commits.",
        ],
        "dataset": {
            "metadata_cases": metadata_cases,
            "seeded_cases": seed["covered_cases"],
            "new_cases": len(records),
            "new_api_success": len(good),
            "new_api_failures": len(records) - len(good),
            "final_cases": total,
            "projects": len(counts),
            "project_counts": {project: row["total"] for project, row in sorted(counts.items())},
            "bugsinpy_commit": seed["bugsinpy_commit"],
        },
        "seed_reference": {
            "source_run_id": seed["source_run_id"],
            "source_artifact_id": seed["source_artifact_id"],
            "source_artifact_digest": seed["source_artifact_digest"],
            "source_head_sha": seed["source_head_sha"],
        },
        "evidence_states": evidence,
        "mapping": mapping,
        "policy_tournament": {
            "obligation_first": {
                "emissions": total,
                "changed_test_proxy_precision": evidence["relevant_test_changed"]["rate"],
                "unchanged_test_proxy_false_obligations": unchanged,
            },
            "suppress_if_any_test_changed": {
                "emissions": no_test_change,
                "note": (
                    "Exact precision is reported only when emissions exist; the preserved seed has no "
                    "no-test-change cases, and new records are retained for direct inspection."
                ),
            },
            "evidence_first_oracle": {
                "states": [
                    "missing_before_fix_proxy",
                    "present_but_modified_proxy",
                    "present_existing_proxy",
                ],
                "note": "Non-deployable upper bound using benchmark paths and future commit metadata.",
            },
        },
        "hypotheses": {
            "H1_unchanged_relevant_test_at_least_25pct": {
                "observed": unchanged / total,
                "passed": unchanged / total >= 0.25,
            },
            "H2_binary_any_test_inadequacy_at_least_10pct": {
                "observed": unchanged / total,
                "passed": unchanged / total >= 0.10,
            },
            "H3_exact_filename_mapping_below_70pct": {
                "observed": mapping["candidate_path_discoverable"]["rate"],
                "passed": mapping["candidate_path_discoverable"]["rate"] < 0.70,
            },
        },
    }


def markdown(summary: dict):
    def pct(value):
        return "n/a" if value is None else f"{100 * value:.1f}%"

    dataset = summary["dataset"]
    lines = [
        "# Autonomous Assurance Laboratory v1 — final 500-case audit",
        "",
        summary["claim_boundary"],
        "",
        f"Final population: **{dataset['final_cases']}** cases across **{dataset['projects']}** projects.",
        "",
        f"The preserved seed contributes {dataset['seeded_cases']} cases; "
        f"{dataset['new_api_success']} newly admitted cases were fetched and classified.",
        "",
        "| Measure | Count | Rate |",
        "|---|---:|---:|",
    ]
    for group in (summary["evidence_states"], summary["mapping"]):
        for name, row in group.items():
            lines.append(f"| {name} | {row['successes']}/{row['total']} | {pct(row['rate'])} |")
    lines += ["", "## Preregistered hypotheses"]
    for name, result in summary["hypotheses"].items():
        lines.append(
            f"- **{name}:** {'PASS' if result['passed'] else 'FAIL'} — {pct(result['observed'])}"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path(__file__).with_name("seed-495-project-counts.json"),
    )
    parser.add_argument("--github-token", default=os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN", "")))
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--csv-output", type=Path, required=True)
    args = parser.parse_args()

    seed = json.loads(args.seed.read_text(encoding="utf-8"))
    current_commit = bugsinpy_commit(args.root)
    if current_commit != seed["bugsinpy_commit"]:
        raise SystemExit(
            f"BugsInPy commit mismatch: expected {seed['bugsinpy_commit']}, got {current_commit}"
        )

    metadata = base.load_meta(args.root)
    metadata_counts = Counter(item.project for item in metadata)
    if len(metadata) != 500 or len(metadata_counts) != 17:
        raise SystemExit(f"expected 500 cases/17 projects, got {len(metadata)}/{len(metadata_counts)}")
    for project, row in seed["project_counts"].items():
        if metadata_counts[project] != row["total"]:
            raise SystemExit(
                f"seed population mismatch for {project}: {row['total']} vs {metadata_counts[project]}"
            )

    missing = [item for item in metadata if item.project not in seed["covered_projects"]]
    if len(missing) != 5 or {item.project for item in missing} != {"httpie"}:
        raise SystemExit(
            f"expected five HTTPie cases outside seed, got {len(missing)} / "
            f"{sorted({item.project for item in missing})}"
        )

    fetched = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for item in missing:
            repo = REPO_ALIASES.get(item.repo, item.repo)
            future = executor.submit(base.fetch_commit, repo, item.fixed_commit_id, args.github_token)
            futures[future] = (item.repo, item.fixed_commit_id)
        for future in as_completed(futures):
            fetched[futures[future]] = future.result()

    records = [base.build(item, fetched[(item.repo, item.fixed_commit_id)]) for item in missing]
    summary = summarize(seed, records, len(metadata))
    payload = {"summary": summary, "new_records": [asdict(record) for record in records]}

    for path in (args.json_output, args.markdown_output, args.csv_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown(summary), encoding="utf-8")
    with args.csv_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(records[0])) if records else [])
        writer.writeheader()
        for record in records:
            row = asdict(record)
            for key, value in row.items():
                if isinstance(value, list):
                    row[key] = json.dumps(value)
            writer.writerow(row)

    print(json.dumps(summary, sort_keys=True))
    valid = (
        summary["dataset"]["final_cases"] == 500
        and summary["dataset"]["projects"] == 17
        and summary["dataset"]["new_api_success"] == 5
    )
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
