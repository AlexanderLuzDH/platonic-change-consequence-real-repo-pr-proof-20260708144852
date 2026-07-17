#!/usr/bin/env python3
"""Run executable cases with Amendment 002's property-aligned path oracle.

The original overconstrained result remains preserved. This correction changes
only the third case's behavioral oracle; commits and targeted mutant stay fixed.
"""
from __future__ import annotations

from dataclasses import replace

import run_pysnooper_cases as base

_PATH_ORACLE = r'''from pathlib import Path
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
    text = path.read_text(encoding="utf-8")
    assert text.strip(), text
    assert "x = 7" in text, text
'''

base.CASES[2] = replace(base.CASES[2], test_code=_PATH_ORACLE)


if __name__ == "__main__":
    raise SystemExit(base.main())
