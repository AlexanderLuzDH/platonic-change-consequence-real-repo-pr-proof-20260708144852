# Amendment 001 — instrument and harness corrections

Date: 2026-07-17

This amendment is recorded after the first CI run (`29552910959`) and before inspecting any result from the corrected upstream-commit instrument.

## Static instrument falsification

The initial static parser treated absence of the benchmark-selected test from `bug_patch.txt` as a proxy that the test existed unchanged. The first run returned 0/500 relevant test files changed.

That interpretation is invalid because the BugsInPy construction explicitly defines `bug_patch.txt` as the isolated source-code patch **excluding test files**. The zero count measured benchmark construction, not test evidence state.

Correction:

- continue to use `bug_patch.txt` only for the isolated changed source paths;
- use each project’s original GitHub repository and `fixed_commit_id` to retrieve the complete human fixed-commit file list;
- classify benchmark-selected tests as added, modified/renamed, or unchanged relative to that upstream commit;
- retain API failures and require at least 95% commit resolution for the corrected corpus gate.

The H1–H3 thresholds remain unchanged.

## Executable harness falsification

The first Python 3.8 run killed only one of three targeted mutants.

Two harness defects were identified before rerun:

1. The Unicode mutant replaced `utf-8` with the same-length string `ascii` immediately after a fixed execution. CPython could reuse timestamp-and-size-valid bytecode, causing the mutant source to be present while the prior compiled code executed.
2. The oldest PySnooper case could not import because its declared runtime dependencies (`future`, `six`, and `decorator`) were not installed.

Corrections:

- purge `__pycache__` directories and `.pyc` files before every execution;
- execute with `-B` and `PYTHONDONTWRITEBYTECODE=1`;
- install pinned historical runtime dependencies in the executable jobs.

The H4 threshold remains at two of three causal gates. Historical-buggy outcomes remain secondary because environment-specific bugs and repository rot can prevent exact reproduction.

## Claim boundary

These corrections repair the measurement process. They are not favorable reinterpretations of the original outputs. The original artifacts remain preserved as failed instruments.