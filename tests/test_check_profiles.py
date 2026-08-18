"""Named check profiles: strictness as a legible, opt-in dial.

`checks:` accepts a profile name or an explicit list; the default is the light
`general` pack, and every profile expands to real, registered checks.
"""
from __future__ import annotations

import pytest

from crossaudit.dcl import builtin, neutral  # noqa: F401  (registers the checks)
from crossaudit.dcl.framework import available
from crossaudit.dcl.profiles import DEFAULT_PROFILE, PROFILES, resolve
from crossaudit.errors import ConfigDenial


def test_default_is_the_light_general_pack():
    assert DEFAULT_PROFILE == "general"
    assert resolve("general") == ["parseable", "declared", "internal", "complete"]


def test_off_profile_disables_all_checks():
    assert resolve("off") == []


def test_science_profile_is_the_structured_science_pack():
    assert resolve("science") == ["schema", "units", "convergence", "provenance"]


def test_an_explicit_list_passes_through_verbatim():
    custom = ["parseable", "complete-strict"]
    assert resolve(custom) == custom
    assert resolve(custom) is not custom      # a copy, not the caller's list


def test_empty_list_means_no_checks_not_the_default():
    assert resolve([]) == []


def test_unknown_profile_name_denies():
    with pytest.raises(ConfigDenial):
        resolve("ultra-strict")


def test_non_string_check_names_deny():
    with pytest.raises(ConfigDenial):
        resolve([1, 2, 3])


def test_every_profile_names_only_registered_checks():
    # No profile may reference a check that does not exist — otherwise selecting
    # it would deny at run time. (documents.py's integrity check is always-on and
    # not selectable, so it is not required to appear here.)
    known = set(available())
    for name, checks in PROFILES.items():
        missing = [c for c in checks if c not in known]
        assert not missing, f"profile {name!r} names unknown checks {missing}"
