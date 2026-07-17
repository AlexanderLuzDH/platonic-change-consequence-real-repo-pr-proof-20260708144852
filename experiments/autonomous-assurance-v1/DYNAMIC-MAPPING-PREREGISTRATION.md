# Dynamic test-mapping pilot — preregistration

Date: 2026-07-17

## Motivation

The final 500-case historical audit found that exact generated filename paths recover only 78/500 BugsInPy-selected test files. The original preregistration states that a passing H3 moves the laboratory toward execution traces, coverage, or history rather than more filename rules.

This pilot tests the smallest execution-grounded alternative on the three already validated PySnooper counterfactual cases. No case, commit, source path, test code, or filename baseline changes for this experiment.

## Unit of analysis

One of the three fixed PySnooper cases:

1. Unicode file output — changed source `pysnooper/tracer.py`, benchmark test `tests/test_chinese.py`.
2. Single custom representation — changed source `pysnooper/tracer.py`, benchmark test `tests/test_pysnooper.py`.
3. String output path — changed source `pysnooper/pysnooper.py`, benchmark test `tests/test_pysnooper.py`.

## Dynamic mapper

Run the compact behavioral test on the human-fixed commit under Python 3.8 while a `sys.setprofile` call profiler records repository-local Python files whose functions are called. PySnooper uses `sys.settrace`; the profiler uses the separate profiling hook so both mechanisms can coexist.

A dynamic mapping hit occurs only when the case’s declared changed source file appears in the recorded repository-local call set and the behavioral test passes.

## Baselines

- Exact generated path, such as `tests/test_<source-stem>.py`.
- Same-stem source/test naming.

## Preregistered hypotheses

### H5 — Dynamic mapping coverage

The call profiler maps at least two of the three passing behavioral tests to their declared changed source file.

### H6 — Dynamic mapping improvement

The dynamic mapper recovers strictly more declared source/test relationships than the exact generated-path baseline.

## Secondary measurements

- Number of repository-local Python files in each dynamic candidate set.
- Whether the result transfers across the two `tracer.py` properties and the older `pysnooper.py` property.
- Any interference between the profiler and PySnooper’s tracing behavior.

## Decision rule

- If H5 and H6 pass, dynamic execution evidence becomes the primary next mapping substrate; filename rules remain fallbacks.
- If the profiler interferes with behavior or fails H5, repair or replace the instrumentation before scaling.
- No broad architecture is added from three cases. Transfer to another project family is required before a general mapping claim.

## Claim boundary

This pilot can demonstrate execution-grounded mapping in three validated cases. It cannot estimate corpus-wide dynamic recall, production overhead, or human usefulness.