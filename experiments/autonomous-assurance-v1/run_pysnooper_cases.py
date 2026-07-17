#!/usr/bin/env python3
"""Execute three history-grounded PySnooper counterfactual cases.

For each case the script checks:
1. the upstream human-fixed commit passes a compact behavioral test;
2. a single targeted mutant of that fixed commit fails the same test; and
3. the BugsInPy historical buggy commit fails the same test when reproducible
   in the current runner environment.

The compact tests are derived from the human regression tests but do not use
PySnooper's test helpers. This keeps the oracle narrow and executable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_URL = "https://github.com/cool-RR/PySnooper.git"


@dataclass(frozen=True)
class Case:
    case_id: str
    property_name: str
    buggy_sha: str
    fixed_sha: str
    source_path: str
    old_fragment: str
    mutant_fragment: str
    test_code: str
    mutation_kind: str


CASES = [
    Case(
        case_id="pysnooper-1-unicode-file-output",
        property_name="non-ASCII traced values can be written to a UTF-8 log file",
        buggy_sha="e21a31162f4c54be693d8ca8260e42393b39abd3",
        fixed_sha="56f22f8ffe1c6b2be4d2cf3ad1987fdb66113da2",
        source_path="pysnooper/tracer.py",
        old_fragment="encoding='utf-8') as output_file",
        mutant_fragment="encoding='ascii') as output_file",
        mutation_kind="fault-family mutant: force ASCII instead of UTF-8",
        test_code=r'''# -*- coding: utf-8 -*-
from pathlib import Path
import tempfile
import pysnooper

with tempfile.TemporaryDirectory(prefix="aa-pysnooper-") as directory:
    path = Path(directory) / "trace.log"
    @pysnooper.snoop(path)
    def traced():
        value = "失败"
        return value
    assert traced() == "失败"
    text = path.read_text(encoding="utf-8")
    assert "失败" in text, text
''',
    ),
    Case(
        case_id="pysnooper-2-single-custom-repr",
        property_name="a single (condition, renderer) tuple is accepted as custom_repr",
        buggy_sha="e21a31162f4c54be693d8ca8260e42393b39abd3",
        fixed_sha="814abc34a098c1b98cb327105ac396f985d2413e",
        source_path="pysnooper/tracer.py",
        old_fragment="            custom_repr = (custom_repr,)",
        mutant_fragment="            custom_repr = custom_repr",
        mutation_kind="exact-fix mutant: remove single-tuple normalization",
        test_code=r'''import io
import pysnooper

stream = io.StringIO()
@pysnooper.snoop(stream, custom_repr=(list, lambda value: "foofoo!"))
def traced():
    value = [1, 2, 3]
    return 7
assert traced() == 7
text = stream.getvalue()
assert "foofoo!" in text, text
''',
    ),
    Case(
        case_id="pysnooper-3-string-path-output",
        property_name="a string output path is opened using the supplied path",
        buggy_sha="6e3d797be3fa0a746fb5b1b7c7fea78eb926c208",
        fixed_sha="15555ed760000b049aff8fecc79d29339c1224c3",
        source_path="pysnooper/pysnooper.py",
        old_fragment="with open(output, 'a') as output_file:",
        mutant_fragment="with open(output_path, 'a') as output_file:",
        mutation_kind="exact historical mutant: restore undefined output_path",
        test_code=r'''from pathlib import Path
import tempfile
import pysnooper

with tempfile.TemporaryDirectory(prefix="aa-pysnooper-") as directory:
    path = Path(directory) / "trace.log"
    @pysnooper.snoop(str(path))
    def traced(value):
        x = 7
        return value + x
    assert traced(8) == 15
    assert path.is_file(), path
    assert "15" in path.read_text(encoding="utf-8")
''',
    ),
]


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
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


def checkout(repo: Path, sha: str) -> None:
    result = run(["git", "checkout", "--force", sha], cwd=repo)
    if result.returncode:
        raise RuntimeError(f"git checkout {sha} failed:\n{result.stdout}\n{result.stderr}")
    clean = run(["git", "clean", "-fdx"], cwd=repo)
    if clean.returncode:
        raise RuntimeError(f"git clean failed:\n{clean.stdout}\n{clean.stderr}")


def write_test(repo: Path, case: Case) -> Path:
    path = repo / "autonomous_assurance_regression.py"
    path.write_text(case.test_code, encoding="utf-8")
    return path


def execute_test(repo: Path, python: str) -> dict[str, object]:
    # Same-size, same-second mutations can otherwise reuse stale CPython bytecode.
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    for bytecode in repo.rglob("*.pyc"):
        bytecode.unlink(missing_ok=True)
    env = {"PYTHONPATH": str(repo), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    result = run([python, "-B", "autonomous_assurance_regression.py"], cwd=repo, env=env)
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def apply_mutation(repo: Path, case: Case) -> dict[str, object]:
    source = repo / case.source_path
    text = source.read_text(encoding="utf-8")
    count = text.count(case.old_fragment)
    if count != 1:
        return {
            "applied": False,
            "match_count": count,
            "source_sha256_before": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
    mutated = text.replace(case.old_fragment, case.mutant_fragment, 1)
    source.write_text(mutated, encoding="utf-8")
    return {
        "applied": True,
        "match_count": count,
        "source_sha256_before": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_sha256_after": hashlib.sha256(mutated.encode("utf-8")).hexdigest(),
    }


def execute_case(case: Case, *, parent: Path, python: str) -> dict[str, object]:
    repo = parent / case.case_id
    clone = run(["git", "clone", "--quiet", REPO_URL, str(repo)], cwd=parent, timeout=300)
    if clone.returncode:
        return {
            "case": asdict(case),
            "infrastructure_error": f"clone failed: {clone.stderr}",
            "causal_gate": False,
            "historical_gate": False,
        }

    checkout(repo, case.fixed_sha)
    write_test(repo, case)
    fixed = execute_test(repo, python)

    mutation = apply_mutation(repo, case)
    mutant = execute_test(repo, python) if mutation.get("applied") else {
        "passed": None,
        "returncode": None,
        "stdout": "",
        "stderr": "mutation not applied",
    }

    checkout(repo, case.buggy_sha)
    write_test(repo, case)
    historical = execute_test(repo, python)

    causal_gate = bool(fixed["passed"] and mutation.get("applied") and not mutant["passed"])
    historical_gate = bool(fixed["passed"] and not historical["passed"])
    return {
        "case": asdict(case),
        "fixed": fixed,
        "mutation": mutation,
        "mutant": mutant,
        "historical_buggy": historical,
        "causal_gate": causal_gate,
        "historical_gate": historical_gate,
        "full_gate": causal_gate and historical_gate,
    }


def render_markdown(payload: dict[str, object]) -> str:
    results = payload["results"]
    lines = [
        "# Autonomous Assurance Lab v1 — executable PySnooper cases",
        "",
        str(payload["claim_boundary"]),
        "",
        "| Case | Fixed | Target mutant | Historical buggy | Causal gate |",
        "|---|---:|---:|---:|---:|",
    ]
    for result in results:
        case = result["case"]
        def mark(value: object) -> str:
            return "PASS" if value else "FAIL"
        if "infrastructure_error" in result:
            lines.append(f"| {case['case_id']} | ERROR | ERROR | ERROR | FAIL |")
            continue
        lines.append(
            f"| {case['case_id']} | {mark(result['fixed']['passed'])} | "
            f"{'KILLED' if not result['mutant']['passed'] else 'SURVIVED'} | "
            f"{'FAILS' if not result['historical_buggy']['passed'] else 'PASSES'} | "
            f"{mark(result['causal_gate'])} |"
        )
    lines += [
        "",
        "A causal gate requires the human-fixed commit to pass and the single targeted mutant to fail. "
        "The historical-buggy result is reported separately because old commits can rot or behave differently "
        "under a modern runner.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=os.environ.get("PYTHON", "python"))
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    managed = None
    if args.workdir is None:
        managed = tempfile.TemporaryDirectory(prefix="autonomous-assurance-")
        parent = Path(managed.name)
    else:
        parent = args.workdir
        parent.mkdir(parents=True, exist_ok=True)

    results = [execute_case(case, parent=parent, python=args.python) for case in CASES]
    payload = {
        "schema_version": 2,
        "kind": "autonomous_assurance_pysnooper_executable_result",
        "claim_boundary": (
            "These are compact executable reproductions derived from three BugsInPy PySnooper cases. "
            "They test fixed-versus-targeted-mutant causality and historical-buggy behavior in the runner; "
            "they are not full-suite reproductions of the entire upstream projects."
        ),
        "python": args.python,
        "harness_controls": ["purge __pycache__ and .pyc before each execution", "run Python with -B and PYTHONDONTWRITEBYTECODE=1"],
        "results": results,
        "summary": {
            "cases": len(results),
            "causal_gates_passed": sum(bool(result.get("causal_gate")) for result in results),
            "historical_gates_passed": sum(bool(result.get("historical_gate")) for result in results),
            "full_gates_passed": sum(bool(result.get("full_gate")) for result in results),
        },
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], sort_keys=True))
    if managed is not None:
        managed.cleanup()
    return 0 if payload["summary"]["causal_gates_passed"] >= 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
