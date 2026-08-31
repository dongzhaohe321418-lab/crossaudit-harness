"""Pull page.py's shipped ZH map, patterns and zhValue() VERBATIM."""
from __future__ import annotations

import pathlib
import re
import sys


def shipped_js(worktree: pathlib.Path) -> str:
    src = (worktree / "src/crossaudit/console/page.py").read_text()
    zh = re.search(r"const ZH=\{.*?\n\};", src, re.S)
    pat = re.search(r"const ZH_PATTERNS=\[.*?\n\];", src, re.S)
    assert zh and pat, "the catalogue moved; this harness is stale"
    m = re.search(r"function zhValue\(", src)
    assert m, "zhValue moved"
    brace = src.index("{", m.start())
    depth = 0
    for i in range(brace, len(src)):
        depth += (src[i] == "{") - (src[i] == "}")
        if depth == 0:
            fn = src[m.start():i + 1]
            break
    return "\n".join([zh.group(0), pat.group(0), fn])


if __name__ == "__main__":
    print(shipped_js(pathlib.Path(sys.argv[1])))
