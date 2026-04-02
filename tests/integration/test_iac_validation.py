from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("TF_VAR_environment", "dev")
    env.setdefault("TF_VAR_region", "eu-west-1")
    env.setdefault("TG_ACCOUNT_ID", "111111111111")
    env.setdefault("AWS_EC2_METADATA_DISABLED", "true")
    env.setdefault("AWS_PAGER", "")
    return env


def test_terragrunt_hcl_validate_env_stack():
    result = subprocess.run(
        [
            "terragrunt",
            "hcl",
            "validate",
            "--working-dir",
            "env",
            "--non-interactive",
            "--no-color",
        ],
        cwd=ROOT,
        env=_base_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_terraform_fmt_check_repo_hcl():
    result = subprocess.run(
        ["terraform", "fmt", "-check", "-recursive", "env", "module"],
        cwd=ROOT,
        env=_base_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_pytest_invocation_has_coverage_flags():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--help"],
        cwd=ROOT,
        env=_base_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--cov" in result.stdout
