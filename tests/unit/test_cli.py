from __future__ import annotations

import os

from collibra_dq_starter import cli


def test_main_calls_deploy_with_target_and_sets_env(monkeypatch):
    called: dict[str, object] = {}

    def fake_deploy(target, *, parallel=False):
        called["target"] = target
        called["parallel"] = parallel

    monkeypatch.setattr(cli, "deploy", fake_deploy)
    monkeypatch.setattr(cli, "destroy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "sys.argv",
        ["dqctl", "--env", "dev", "--region", "eu-west-1", "deploy", "--target", "full"],
    )

    assert cli.main() == 0
    assert called["target"] == "full"
    assert called["parallel"] is False
    assert os.environ["TF_VAR_environment"] == "dev"
    assert os.environ["TF_VAR_region"] == "eu-west-1"


def test_main_calls_deploy_with_parallel_flag(monkeypatch):
    called: dict[str, object] = {}

    def fake_deploy(target, *, parallel=False):
        called["target"] = target
        called["parallel"] = parallel

    monkeypatch.setattr(cli, "deploy", fake_deploy)
    monkeypatch.setattr(cli, "destroy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("sys.argv", ["dqctl", "deploy", "--target", "full", "--parallel"])

    assert cli.main() == 0
    assert called["target"] == "full"
    assert called["parallel"] is True


def test_main_calls_destroy_with_yes(monkeypatch):
    called: dict[str, object] = {}

    def fake_destroy(target, *, auto_approve=False, parallel=False):
        called["target"] = target
        called["auto_approve"] = auto_approve
        called["parallel"] = parallel

    monkeypatch.setattr(cli, "destroy", fake_destroy)
    monkeypatch.setattr(cli, "deploy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("sys.argv", ["dqctl", "destroy", "--target", "all", "--yes"])

    assert cli.main() == 0
    assert called["target"] == "all"
    assert called["auto_approve"] is True
    assert called["parallel"] is False


def test_main_calls_destroy_with_parallel_flag(monkeypatch):
    called: dict[str, object] = {}

    def fake_destroy(target, *, auto_approve=False, parallel=False):
        called["target"] = target
        called["parallel"] = parallel

    monkeypatch.setattr(cli, "destroy", fake_destroy)
    monkeypatch.setattr(cli, "deploy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("sys.argv", ["dqctl", "destroy", "--target", "addon", "--parallel"])

    assert cli.main() == 0
    assert called["parallel"] is True


def test_main_returns_130_on_keyboard_interrupt(monkeypatch):
    def fake_deploy(_target, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "deploy", fake_deploy)
    monkeypatch.setattr("sys.argv", ["dqctl", "deploy"])

    assert cli.main() == 130


def test_main_returns_1_on_runtime_error(monkeypatch):
    def fake_deploy(_target, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "deploy", fake_deploy)
    monkeypatch.setattr("sys.argv", ["dqctl", "deploy"])

    assert cli.main() == 1
