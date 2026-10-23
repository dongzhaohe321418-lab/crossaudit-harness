"""A configured ``key_env`` is stripped from every non-provider child
(``app_keys.child_env``), so the loader refuses names that are not key
variables at all. D10 mutations: drop the reserved-name check in
``config._role`` -> the PATH test; drop the shape check -> the space test;
widen ``_KEY_ENV_RESERVED`` to swallow ordinary names -> the odd-name test.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from crossaudit import config
from crossaudit.errors import ConfigDenial


def _with_auditor_key_env(science: Path, name: str) -> Path:
    path = science / "crossaudit.yml"
    text = path.read_text(encoding="utf-8")
    assert "  key_env: CROSSAUDIT_AUDITOR_KEY\n" in text
    path.write_text(text.replace("  key_env: CROSSAUDIT_AUDITOR_KEY\n",
                                 f"  key_env: {name}\n", 1), encoding="utf-8")
    return path


def test_a_key_env_naming_PATH_is_refused_before_it_could_be_stripped_from_children(science):
    path = _with_auditor_key_env(science, "PATH")
    with pytest.raises(ConfigDenial) as excinfo:
        config.load(path)
    assert "auditor.key_env must name a variable that holds only a key; 'PATH' is not one" in str(excinfo.value)


def test_a_key_env_with_a_space_is_refused_as_not_a_variable_name(science):
    path = _with_auditor_key_env(science, "'MY KEY'")
    with pytest.raises(ConfigDenial) as excinfo:
        config.load(path)
    assert "auditor.key_env must name a variable that holds only a key" in str(excinfo.value)


def test_an_odd_but_valid_key_env_name_still_loads_and_is_registered(science):
    from crossaudit import app_keys

    path = _with_auditor_key_env(science, "PROJECT_PROVIDER_SECRET")
    cfg = config.load(path)
    assert cfg.auditor.key_env == "PROJECT_PROVIDER_SECRET"
    assert "PROJECT_PROVIDER_SECRET" in app_keys.configured_key_names()
