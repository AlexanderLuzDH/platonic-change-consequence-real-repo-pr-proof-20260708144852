#!/usr/bin/env python3
"""Compare dynamic call mapping with filename baselines on PySnooper cases."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

import run_corrected_pysnooper as corrected_cases
import run_corrected_static as mapping

base = corrected_cases.base
BENCHMARK_TESTS = {
    "pysnooper-1-unicode-file-output": "tests/test_chinese.py",
    "pysnooper-2-single-custom-repr": "tests/test_pysnooper.py",
    "pysnooper-3-string-path-output": "tests/test_pysnooper.py",
}


def run(command, *, cwd: Path, env=None, timeout: int = 240):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        command,
        cwd=cwd,
        env=merged,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def checkout(repo: Path, sha: str):
    result = run(["git", "checkout", "--force", sha], cwd=repo)
    if result.returncode:
        raise RuntimeError(result.stderr)
    result = run(["git", "clean", "-fdx"], cwd=repo)
    if result.returncode:
        raise RuntimeError(result.stderr)


def profile_script(test_code: str) -> str:
    return f'''from __future__ import annotations
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEEN = set()
ERROR = None
TEST_CODE = {test_code!r}


def profiler(frame, event, arg):
    if event != "call":
        return
    filename = frame.f_code.co_filename
    if not filename or filename.startswith("<"):
        return
    try:
        relative = Path(filename).resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        return
    if relative.endswith(".py") and not relative.startswith("autonomous_assurance_"):
        SEEN.add(relative)


sys.setprofile(profiler)
try:
    namespace = {{"__name__": "__main__"}}
    exec(compile(TEST_CODE, "autonomous_assurance_behavior.py", "exec"), namespace, namespace)
except BaseException:
    ERROR = traceback.format_exc()
finally:
    sys.setprofile(None)
    Path("executed-files.json").write_text(
        json.dumps({{"executed_files": sorted(SEEN), "error": ERROR}}, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )

if ERROR:
    raise SystemExit(ERROR)
'''


def execute_case(case, *, parent: Path, python: str):
    repo = parent / case.case_id
    clone = run(["git", "clone", "--quiet", base.REPO_URL, str(repo)], cwd=parent, timeout=300)
    if clone.returncode:
        return {
            "case_id": case.case_id,
            "infrastructure_error": clone.stderr,
            "test_passed": False,
            "dynamic_hit": False,
        }
    checkout(repo, case.fixed_sha)
    (repo / "autonomous_assurance_profiled.py").write_text(
        profile_script(case.test_code), encoding="utf-8"
    )
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    env = {
        "PYTHONPATH": str(repo),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = run([python, "-B", "autonomous_assurance_profiled.py"], cwd=repo, env=env)
    profile_path = repo / "executed-files.json"
    profile = (
        json.loads(profile_path.read_text(encoding="utf-8"))
        if profile_path.is_file()
        else {"executed_files": [], "error": "profile artifact missing"}
    )
    benchmark_test = BENCHMARK_TESTS[case.case_id]
    exact_hit = benchmark_test in mapping.base.candidates(case.source_path)
    source_stem = PurePosixPath(case.source_path).stem.lower()
    test_stem = PurePosixPath(benchmark_test).stem.lower().replace("test_", "").replace("_test", "")
    same_stem_hit = source_stem in test_stem or test_stem in source_stem
    executed = sorted(profile["executed_files"])
    return {
        "case_id": case.case_id,
        "property": case.property_name,
        "fixed_sha": case.fixed_sha,
        "changed_source": case.source_path,
        "benchmark_test": benchmark_test,
        "test_passed": result.returncode == 0,
        "dynamic_hit": result.returncode == 0 and case.source_path in executed,
        "dynamic_candidate_count": len(executed),
        "dynamic_candidates": executed,
        "exact_generated_path_hit": exact_hit,
        "same_stem_hit": same_stem_hit,
        "stdout": result.stdout[-3000:],
        "stderr": result.stderr[-3000:],
        "profile_error": profile.get("error"),
    }


def markdown(payload):
    lines = [
        "# Dynamic test-mapping pilot",
        "",
        payload["claim_boundary"],
        "",
        "| Case | Test passed | Dynamic | Exact path | Same stem | Dynamic candidate files |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        mark = lambda value: "PASS" if value else "FAIL"
        lines.append(
            f"| {row['case_id']} | {mark(row['test_passed'])} | {mark(row['dynamic_hit'])} | "
            f"{mark(row['exact_generated_path_hit'])} | {mark(row['same_stem_hit'])} | "
            f"{row['dynamic_candidate_count']} |"
        )
    lines += ["", "## Preregistered hypotheses"]
    for name, result in payload["hypotheses"].items():
        lines.append(
            f"- **{name}:** {'PASS' if result['passed'] else 'FAIL'} — {result['observed']}"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=os.getenv("PYTHON", "python"))
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    managed = None
    if args.workdir is None:
        managed = tempfile.TemporaryDirectory(prefix="dynamic-mapping-")
        parent = Path(managed.name)
    else:
        parent = args.workdir
        parent.mkdir(parents=True, exist_ok=True)

    results = [execute_case(case, parent=parent, python=args.python) for case in base.CASES]
    dynamic_hits = sum(bool(row.get("dynamic_hit")) for row in results)
    exact_hits = sum(bool(row.get("exact_generated_path_hit")) for row in results)
    same_stem_hits = sum(bool(row.get("same_stem_hit")) for row in results)
    payload = {
        "schema_version": 1,
        "kind": "autonomous_assurance_dynamic_mapping_pilot",
        "claim_boundary": (
            "Three fixed PySnooper cases under a Python call profiler. "
            "This is not a corpus-wide recall or performance estimate."
        ),
        "results": results,
        "summary": {
            "cases": len(results),
            "tests_passed": sum(bool(row.get("test_passed")) for row in results),
            "dynamic_hits": dynamic_hits,
            "exact_generated_path_hits": exact_hits,
            "same_stem_hits": same_stem_hits,
        },
        "hypotheses": {
            "H5_dynamic_mapping_at_least_two_of_three": {
                "observed": f"{dynamic_hits}/3",
                "passed": dynamic_hits >= 2,
            },
            "H6_dynamic_strictly_beats_exact_path": {
                "observed": f"{dynamic_hits}>{exact_hits}",
                "passed": dynamic_hits > exact_hits,
            },
        },
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], sort_keys=True))
    if managed is not None:
        managed.cleanup()
    return 0 if all(item["passed"] for item in payload["hypotheses"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
