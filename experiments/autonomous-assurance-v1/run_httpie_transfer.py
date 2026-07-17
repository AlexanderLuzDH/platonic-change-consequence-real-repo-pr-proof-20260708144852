#!/usr/bin/env python3
"""Execute and profile the preregistered HTTPie bug-1 transfer case."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_URL = "https://github.com/httpie/cli.git"
BUGGY_SHA = "001bda19450ad85c91345eea3cfa3991e1d492ba"
FIXED_SHA = "5300b0b490b8db48fac30b5e32164be93dc574b7"
SOURCE_PATH = "httpie/downloads.py"
BENCHMARK_TEST = "tests/test_downloads.py"
FIXED_FRAGMENT = """        try_filename = trim_filename_if_needed(filename, extra=len(suffix))
        try_filename += suffix
        if not exists(try_filename):
            return try_filename
"""
MUTANT_FRAGMENT = """        if not exists(filename + suffix):
            return filename + suffix
"""
TEST_CODE = r'''import httpie.downloads as downloads

downloads.get_filename_max_length = lambda directory: 10
result = downloads.get_unique_filename("A" * 20, exists=lambda filename: False)
assert result == "A" * 10, result
'''


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


def clean_bytecode(repo: Path):
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    for bytecode in repo.rglob("*.pyc"):
        bytecode.unlink(missing_ok=True)


def checkout(repo: Path, sha: str):
    result = run(["git", "checkout", "--force", sha], cwd=repo)
    if result.returncode:
        raise RuntimeError(result.stderr)
    result = run(["git", "clean", "-fdx"], cwd=repo)
    if result.returncode:
        raise RuntimeError(result.stderr)


def write_behavior(repo: Path):
    (repo / "autonomous_assurance_behavior.py").write_text(TEST_CODE, encoding="utf-8")


def execute(repo: Path, python: str):
    clean_bytecode(repo)
    env = {
        "PYTHONPATH": str(repo),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = run([python, "-B", "autonomous_assurance_behavior.py"], cwd=repo, env=env)
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[-3000:],
        "stderr": result.stderr[-3000:],
    }


def mutate(repo: Path):
    path = repo / SOURCE_PATH
    text = path.read_text(encoding="utf-8")
    matches = text.count(FIXED_FRAGMENT)
    if matches != 1:
        return {"applied": False, "match_count": matches}
    mutated = text.replace(FIXED_FRAGMENT, MUTANT_FRAGMENT, 1)
    path.write_text(mutated, encoding="utf-8")
    return {
        "applied": True,
        "match_count": matches,
        "before_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "after_sha256": hashlib.sha256(mutated.encode("utf-8")).hexdigest(),
    }


def profiler_source():
    return '''from __future__ import annotations
import json
import runpy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEEN = set()
ERROR = None


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
    runpy.run_path(str(ROOT / "autonomous_assurance_behavior.py"), run_name="__main__")
except BaseException:
    ERROR = traceback.format_exc()
finally:
    sys.setprofile(None)
    Path("executed-files.json").write_text(
        json.dumps({"executed_files": sorted(SEEN), "error": ERROR}, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )
if ERROR:
    raise SystemExit(ERROR)
'''


def profile(repo: Path, python: str):
    clean_bytecode(repo)
    (repo / "autonomous_assurance_profiled.py").write_text(profiler_source(), encoding="utf-8")
    env = {
        "PYTHONPATH": str(repo),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = run([python, "-B", "autonomous_assurance_profiled.py"], cwd=repo, env=env)
    payload_path = repo / "executed-files.json"
    payload = (
        json.loads(payload_path.read_text(encoding="utf-8"))
        if payload_path.is_file()
        else {"executed_files": [], "error": "profile artifact missing"}
    )
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "executed_files": payload["executed_files"],
        "profile_error": payload.get("error"),
        "stdout": result.stdout[-3000:],
        "stderr": result.stderr[-3000:],
    }


def markdown(payload):
    summary = payload["summary"]
    lines = [
        "# HTTPie autonomous transfer case",
        "",
        payload["claim_boundary"],
        "",
        "| Check | Result |",
        "|---|---:|",
        f"| Human-fixed commit passes | {'PASS' if summary['fixed_passed'] else 'FAIL'} |",
        f"| Target mutant killed | {'PASS' if summary['mutant_killed'] else 'FAIL'} |",
        f"| Historical buggy commit fails | {'PASS' if summary['historical_buggy_failed'] else 'FAIL'} |",
        f"| Dynamic mapper hits `{SOURCE_PATH}` | {'PASS' if summary['dynamic_hit'] else 'FAIL'} |",
        f"| Dynamic candidate files | {summary['dynamic_candidate_count']} |",
        "",
        "## Preregistered hypotheses",
    ]
    for name, result in payload["hypotheses"].items():
        lines.append(f"- **{name}:** {'PASS' if result['passed'] else 'FAIL'}")
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
        managed = tempfile.TemporaryDirectory(prefix="httpie-transfer-")
        parent = Path(managed.name)
    else:
        parent = args.workdir
        parent.mkdir(parents=True, exist_ok=True)
    repo = parent / "httpie-cli"
    clone = run(["git", "clone", "--quiet", REPO_URL, str(repo)], cwd=parent, timeout=300)
    if clone.returncode:
        raise SystemExit(clone.stderr)

    checkout(repo, FIXED_SHA)
    write_behavior(repo)
    fixed = execute(repo, args.python)
    dynamic = profile(repo, args.python)
    mutation = mutate(repo)
    mutant = execute(repo, args.python) if mutation.get("applied") else {"passed": None}

    checkout(repo, BUGGY_SHA)
    write_behavior(repo)
    historical = execute(repo, args.python)

    summary = {
        "fixed_passed": bool(fixed["passed"]),
        "mutant_killed": bool(mutation.get("applied") and not mutant.get("passed")),
        "historical_buggy_failed": bool(not historical["passed"]),
        "dynamic_hit": bool(dynamic["passed"] and SOURCE_PATH in dynamic["executed_files"]),
        "dynamic_candidate_count": len(dynamic["executed_files"]),
    }
    payload = {
        "schema_version": 1,
        "kind": "autonomous_assurance_httpie_transfer",
        "claim_boundary": (
            "One BugsInPy HTTPie case testing fixed-versus-mutant causality and call-profile mapping. "
            "This is not a corpus-wide transfer estimate."
        ),
        "case": {
            "buggy_sha": BUGGY_SHA,
            "fixed_sha": FIXED_SHA,
            "source_path": SOURCE_PATH,
            "benchmark_test": BENCHMARK_TEST,
            "property": "overlong download filenames are trimmed before uniqueness checks",
        },
        "fixed": fixed,
        "mutation": mutation,
        "mutant": mutant,
        "historical_buggy": historical,
        "dynamic": dynamic,
        "summary": summary,
        "hypotheses": {
            "H7_cross_project_causal_transfer": {
                "passed": summary["fixed_passed"] and summary["mutant_killed"]
            },
            "H8_cross_project_dynamic_mapping_transfer": {"passed": summary["dynamic_hit"]},
        },
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(markdown(payload), encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    if managed is not None:
        managed.cleanup()
    return 0 if all(item["passed"] for item in payload["hypotheses"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
