"""A configured ``key_env`` is stripped from every non-provider child
(``app_keys.child_env``), so the loader refuses names that are not key
variables at all. D10 mutations: drop the reserved-name check in
``config._role`` -> the PATH test; drop the shape check -> the space test;
widen ``_KEY_ENV_RESERVED`` to swallow ordinary names -> the odd-name test.

The direct generator row (review terra-r2, P2) does not go through ``_role``;
``config.load`` runs the same ``_key_env_name`` check on it before
registration. Each generator test below names its own mutation.
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


def _with_generator_key_env(science: Path, value: str) -> Path:
    path = science / "crossaudit.yml"
    text = path.read_text(encoding="utf-8")
    anchor = "generator:\n  vendor: openai\n"
    assert anchor in text
    path.write_text(text.replace(anchor, anchor + f"  key_env: {value}\n", 1),
                    encoding="utf-8")
    return path


def test_a_generator_key_env_naming_PATH_is_refused_and_never_registered(science):
    """Mutation: drop the `_key_env_name(generator_key_env, ...)` call in
    `config.load` -> the load succeeds and PATH is registered (this goes red)."""
    from crossaudit import app_keys

    path = _with_generator_key_env(science, "PATH")
    with pytest.raises(ConfigDenial) as excinfo:
        config.load(path)
    assert ("generator.key_env must name a variable that holds only a key; "
            "'PATH' is not one") in str(excinfo.value)
    assert "PATH" not in app_keys.configured_key_names()
    assert "PATH" in app_keys.child_env({"PATH": "/bin"})


def test_a_non_string_generator_key_env_is_refused_not_a_type_error(science):
    """Mutation: the same call dropped -> the load succeeds with
    `generator_key_env == 7` and a later lookup raises TypeError; or the
    validator's `isinstance(value, str)` dropped -> `_KEY_ENV_NAME.match(7)`
    raises TypeError here instead of a ConfigDenial (either way red)."""
    path = _with_generator_key_env(science, "7")
    with pytest.raises(ConfigDenial) as excinfo:
        config.load(path)
    assert ("generator.key_env must name a variable that holds only a key; "
            "7 is not one") in str(excinfo.value)


def test_an_odd_but_valid_generator_key_env_loads_and_is_registered(science):
    """Mutation: passing `None` instead of `generator_key_env` to
    `_register_key_names` -> this goes red (the name is not registered)."""
    from crossaudit import app_keys

    path = _with_generator_key_env(science, "GEN_CREDENTIAL")
    cfg = config.load(path)
    assert cfg.generator_key_env == "GEN_CREDENTIAL"
    assert "GEN_CREDENTIAL" in app_keys.configured_key_names()
    assert "GEN_CREDENTIAL" not in app_keys.child_env({"GEN_CREDENTIAL": "x",
                                                       "PATH": "/bin"})


def test_an_absent_generator_key_env_still_loads_with_the_default(science):
    """The direct generator row's `key_env` stays optional. Mutation: validating
    it unconditionally (`None` refused) -> this goes red."""
    cfg = config.load(science / "crossaudit.yml")
    assert cfg.generator_key_env is None
