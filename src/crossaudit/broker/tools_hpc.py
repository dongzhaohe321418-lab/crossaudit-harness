"""Phase 4 SSH/HPC tools — the existing hpc.MANAGER, behind the broker.

Reads of a job the user already has (``hpc_status``/``hpc_output``) are wrapped
as read tools; ``hpc_submit`` launches remote work that costs resources, so it is
Level 5 and always ``needs_approval`` — the broker never auto-submits, and the
build never fires a real submission. Evidence records the job id and a hash of
the submitted manifest, never secrets.
"""
from __future__ import annotations

from .. import hpc
from ..config import Config
from ..policy.tokens import CapabilityToken
from ..receipt.schema import digest
from .registry import ToolError, ToolRegistry, ToolSpec


def hpc_status(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    job_id = str(args.get("job_id", "") or "")
    if not job_id:
        raise ToolError("hpc_status needs a 'job_id'")
    return hpc.MANAGER.logs(cfg, job_id)


def hpc_output(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    job_id = str(args.get("job_id", "") or "")
    if not job_id:
        raise ToolError("hpc_output needs a 'job_id'")
    return {"job_id": job_id, "outputs": hpc.MANAGER.outputs(cfg, job_id)}


def hpc_submit(cfg: Config, args: dict, token: CapabilityToken) -> dict:
    manifest = args.get("manifest") or args.get("payload")
    if not isinstance(manifest, dict) or not manifest:
        raise ToolError("hpc_submit needs a non-empty 'manifest'")
    result = hpc.MANAGER.submit(cfg, manifest)
    job_id = str(result.get("job_id") or result.get("id") or "")
    return {"job_id": job_id, "manifest_sha256": digest(manifest)}


def hpc_submit_preview(cfg: Config, args: dict) -> str:
    """A summary of the job that would be submitted, for the approval card."""
    manifest = args.get("manifest") or args.get("payload")
    if not isinstance(manifest, dict):
        return "submit HPC job (invalid manifest)"
    host = str(manifest.get("host") or manifest.get("host_id") or "")
    cmd = str(manifest.get("cmd") or manifest.get("command") or "")[:400]
    keys = ", ".join(sorted(str(k) for k in manifest))
    return (f"submit HPC job\nhost: {host or '(default)'}\ncmd: {cmd or '(none)'}\n"
            f"manifest keys: {keys}")


def register_hpc(registry: ToolRegistry) -> ToolRegistry:
    registry.register(ToolSpec(
        name="hpc_status", level=1, writes=False, needs_network=True,
        handler=hpc_status, summary="Read an HPC job's status/logs."))
    registry.register(ToolSpec(
        name="hpc_output", level=1, writes=False, needs_network=True,
        handler=hpc_output, summary="List an HPC job's output files."))
    registry.register(ToolSpec(
        name="hpc_submit", level=5, writes=True, needs_network=True,
        handler=hpc_submit, evidence_fields=("job_id", "manifest_sha256"),
        preview=hpc_submit_preview,
        summary="Submit an HPC job — costs resources, always needs approval."))
    return registry
