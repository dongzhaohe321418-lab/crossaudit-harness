"""E12 corpus preparation (no model calls): E7's feasibility check and hidden-input recorder, unchanged, on E12's
corpus. Writes feasibility.json and hidden_inputs.json here. Usage: python prepare12.py <executor python>"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "e7")]
import corpus12                                    # noqa: E402

corpus12.install()
for script in ("check7.py", "record7.py"):
    runpy.run_path(str(HERE.parent / "e7" / script), run_name="__main__")
