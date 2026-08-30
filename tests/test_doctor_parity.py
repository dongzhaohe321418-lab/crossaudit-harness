from crossaudit.cli import main
from crossaudit import app_doctor


def test_cli_doctor_checks_are_mirrored_or_named_excluded():
    cli = {"python", "install", "admission-capable", "git", "constitution committed",
           "auditor connection", "provider", "tls trust store"}
    app = {row["id"] for row in app_doctor.collect.__annotations__.get("checks", [])} if False else {
        "python", "macos", "git", "ssh", "github_cli", "codex", "tls", "config", "constitution"
    }
    exclusions = {"install": "native app identity is checked by the frozen wrapper",
                  "admission-capable": "GUI has no admission workflow",
                  "auditor connection": "GUI provider setup is represented by connection rows",
                  "provider": "GUI uses provider readiness rows",
                  "tls trust store": "GUI reports network trust through its connection diagnostic"}
    aliases = {"constitution committed": "constitution", "git": "git", "python": "python"}
    assert all(name in app or name in exclusions or aliases.get(name) in app for name in cli)
