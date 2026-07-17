# Dynamic mapping amendment 001 — preserve a real behavioral source file

Date: 2026-07-17

This amendment is recorded after workflow run `29554130861` and before rerunning the dynamic pilot.

## Observed result

The preregistered dynamic mapper recovered the declared changed source in the first two cases and beat the exact generated-path baseline 2-to-1. The third fixed commit failed before its property assertion because the profiler wrapper executed the unchanged behavioral test using:

```python
exec(compile(TEST_CODE, "autonomous_assurance_behavior.py", "exec"), ...)
```

No file with that name existed. The old PySnooper implementation resolves source lines from `frame.f_code.co_filename`; it therefore raised `NotImplementedError` when it could not read the synthetic source.

The same third behavioral test passes in the ordinary executable counterfactual job. The failure is specific to the dynamic harness’s in-memory execution context, not the declared string-path property or the call profiler’s mapping result.

## Correction

- write the unchanged compact behavioral test to a real `autonomous_assurance_behavior.py` file;
- install the call profiler in a separate wrapper;
- execute the real file with `runpy.run_path(..., run_name="__main__")`;
- retain the same fixed commits, changed source paths, tests, filename baselines, profiler, and H5/H6 thresholds.

The 2/3 artifact remains preserved as a failed execution-context instrument. The corrected result is admitted only if all behavioral tests run normally and the original hypotheses still pass.