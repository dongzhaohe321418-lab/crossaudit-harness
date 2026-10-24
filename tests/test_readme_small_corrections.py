"""Small README/product disagreements from the acceptance run (D172 ruling 7).

(b) A non-interactive `init` (claim C03: `--no-console`, vendors on the
command line, stdin not a terminal) cannot prompt for keys and writes no keys
file, yet its summary said only "Ready". It now says where keys come from.
(f) A provider refusal named `--allow-insecure-localhost`, a flag that never
existed. These run the real `init` and the real `egress_check`.

D10 mutations (checked by hand): delete the `else:` branch that prints
`next.keys_from_env` in `wizard.run` and the two init cases go red; restore
the old sentence in `egress_check` and the two egress cases go red.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import init_project, with_keys  # noqa: E402

from crossaudit.cli import i18n, wizard  # noqa: E402
from crossaudit.errors import ConfigDenial  # noqa: E402
from crossaudit.providers.base import egress_check  # noqa: E402


def test_non_interactive_init_says_no_keys_file_was_written(tmp_path, monkeypatch,
                                                            capsys):
    with_keys(monkeypatch)
    init_project(tmp_path, monkeypatch)
    out = " ".join(capsys.readouterr().out.replace("│", " ").split())
    assert ("No keys file was written: keys are read from "
            "CROSSAUDIT_AUDITOR_KEY and CROSSAUDIT_GENERATOR_KEY in the environment") in out
    assert not wizard.keys_file().exists()


def test_the_sentence_is_translated(tmp_path, monkeypatch, capsys):
    from crossaudit.cli import main

    with_keys(monkeypatch)
    monkeypatch.chdir(tmp_path)
    try:
        assert main.main(["init", "proj", "--lang", "zh", "--no-console",
                          "--auditor-vendor", "openai", "--auditor-model", "gpt-5.6-terra",
                          "--generator-vendor", "anthropic",
                          "--generator-model", "claude-sonnet-4-6"]) == 0
    finally:
        i18n.set_language("en")
    out = " ".join(capsys.readouterr().out.replace("│", " ").split())
    assert "没有写入密钥文件" in out


@pytest.mark.parametrize("url,allow_loopback,expected", [
    ("http://api.example.com/v1", True,
     "only HTTPS is allowed, except to a loopback address set as `base_url:` with "
     "CROSSAUDIT_ALLOW_CUSTOM_ENDPOINT=1"),
    ("http://127.0.0.1:9/v1", False, "this request accepts HTTPS only, even on loopback"),
])
def test_the_plaintext_refusal_names_what_exists(url, allow_loopback, expected):
    with pytest.raises(ConfigDenial) as caught:
        egress_check(url, builtin_origin="https://api.example.com",
                     allow_custom=True, allow_insecure_localhost=allow_loopback)
    assert expected in caught.value.reason
    assert "--allow-insecure-localhost" not in caught.value.reason
    assert i18n.denial_zh(caught.value.reason) != caught.value.reason


def test_loopback_plain_http_still_needs_the_custom_endpoint_opt_in():
    """Behaviour unchanged: the adapters' loopback allowance is not an opt-in."""
    assert egress_check("http://127.0.0.1:9/v1", builtin_origin="https://api.example.com",
                        allow_custom=True, allow_insecure_localhost=True) == "http://127.0.0.1:9"
    with pytest.raises(ConfigDenial, match="not this provider's built-in origin"):
        egress_check("http://127.0.0.1:9/v1", builtin_origin="https://api.example.com",
                     allow_custom=False, allow_insecure_localhost=True)
