"""P8 — the top bar shows a clean project name, not the owner/repo GitHub slug.

The slug (``lab/science`` / ``dongzhaohe321418-lab/DEMO``) is demoted to the
hover title; the visible name is the repository/project name alone.
"""
from __future__ import annotations

from crossaudit.console.page import PAGE
from crossaudit.console.server import _project_title, snapshot


def test_project_title_strips_the_org_slug(cfg):
    # conftest's science_repo is "lab/science" → the clean name is "science".
    assert _project_title(cfg) == "science"


def test_snapshot_exposes_clean_title_and_keeps_the_slug(cfg):
    snap = snapshot(cfg)
    assert snap["title"] == "science"           # clean name for the top bar
    assert snap["project"] == "lab/science"     # full slug preserved
    assert snap["folder"] == cfg.root.name       # workspace folder for the tooltip


def test_page_uses_the_clean_title_and_a_prominent_stop():
    # Top bar renders d.title (with the slug on hover), not d.project directly.
    assert "d.title || d.project" in PAGE
    assert "project-switcher" in PAGE
    # A prominent Stop in the live run card, reusing the vetted cancel flow.
    assert "run-stop" in PAGE and "requestStop" in PAGE
    # One-time, flicker-free shell entrance (guarded by a boot flag).
    assert "booted" in PAGE and "shell-in" in PAGE
