from __future__ import annotations

import os

import pytest

from collibra_dq_starter.shell import CommandError, run


def test_run_returns_command_result():
    result = run(["bash", "-lc", "printf 'ok'"], check=True)
    assert result.returncode == 0
    assert result.stdout.strip().endswith("ok")
    assert result.stderr == ""


def test_run_raises_command_error_when_check_true():
    with pytest.raises(CommandError) as exc_info:
        run(["bash", "-lc", "echo fail >&2; exit 9"], check=True)
    message = str(exc_info.value)
    assert "Command failed (9)" in message
    assert "fail" in message


def test_run_merges_environment_overrides(monkeypatch):
    key = "DQ_TEST_ENV_MERGE"
    monkeypatch.setenv(key, "outer")
    result = run(["bash", "-lc", f"printf %s ${key}"], check=True, env={key: "inner"})
    assert result.stdout.strip().endswith("inner")
