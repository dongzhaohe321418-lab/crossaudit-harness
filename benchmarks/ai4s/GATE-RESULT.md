# SciCode parse/execution gate — 2026-09-23, before any model call

Harness: `harness/scicode_exec.py`, mirroring SciCode's own `eval/inspect_ai/scicode.py` assembly
(steps 1..k of code, then `targets = process_hdf5_to_tuple(step, n)`, then each test with
`target = targets[i]`). Environment: Python 3.13 venv (`.venv`), numpy/scipy/sympy/h5py, SciCode
installed editable. Data: HuggingFace `SciCode1/SciCode` (Apache-2.0) problems_dev (15 main, 50
sub) and problems_test (65 main, 291 sub, no gold code); `test_data.h5` (1.05 GB, 338 step groups)
from the benchmark's Google Drive folder.

Gold code on the dev split (the only split that publishes it), official three skips applied:
**48 pass, 2 fail, 0 timeout.**

* `78.3` — the gold `pendulum_analysis` selects its time step by measuring wall-clock time
  (`time.time()` around an RK4 run), so its expected output depends on machine speed. Not
  reproducible by construction.
* `70.8` — `probabilities_3nu` fails an `np.allclose` assertion in this environment; not yet
  diagnosed (numerics or library version).

Consequence registered for the design: the test split has no gold code, so a step's tests cannot
be shown passable in this environment a priori; a step enters the defect or correct stratum only
if at least one candidate passes its tests (proof of passability). The dev-split rate of
environment-unpassable steps, 2/50, is the prior for how many test-split steps this excludes.
