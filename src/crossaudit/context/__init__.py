"""Context-shaping helpers: what the generator actually sees each round.

Pure, deterministic, stdlib-only utilities that keep the generator prompt from
growing without bound — symbol outlines for large files, so a big or file-heavy
project does not inline its entire working tree verbatim every round. Nothing
here touches the auditor, the ledger, or the committed work; it only shapes the
read-only view handed to the generator, and every elision is recoverable with
the audited file_read tool.
"""
from .outline import MAX_FILE_BYTES, MAX_WORK_BYTES, outline, shape_work

__all__ = ["MAX_FILE_BYTES", "MAX_WORK_BYTES", "outline", "shape_work"]
