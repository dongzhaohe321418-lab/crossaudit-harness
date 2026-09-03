"""Put the benchmark package on sys.path.

These tests are deliberately *not* under the repo's ``tests/`` tree: that conftest scrubs
every ``CROSSAUDIT_*_KEY`` and blocks non-loopback sockets, which is right for the product's
suite and wrong for a harness whose whole job is to make real provider calls.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
