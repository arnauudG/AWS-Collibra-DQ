from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.aws]

ROOT = Path(__file__).resolve().parents[3]
ACK = "I_UNDERSTAND_THIS_WILL_DEPLOY_AND_DESTROY"


def _require_aws_smoke_env() -> tuple[str, str]:
    if os.environ.get("RUN_AWS_INTEGRATION") != "1":
        pytest.skip("AWS integration tests are disabled. Set RUN_AWS_INTEGRATION=1 to enable.")
    if os.environ.get("DQ_AWS_SMOKE_ACK") != ACK:
        pytest.skip(
            "AWS smoke test requires explicit acknowledgement via "
            f"DQ_AWS_SMOKE_ACK={ACK}."
        )

    env = os.environ.get("DQ_AWS_ENV") or os.environ.get("TF_VAR_environment")
    region = os.environ.get("DQ_AWS_REGION") or os.environ.get("TF_VAR_region")
    if not env or not region:
        pytest.skip("Set DQ_AWS_ENV and DQ_AWS_REGION (or TF_VAR_environment/TF_VAR_region).")
    return env, region


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "collibra_dq_starter.cli", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "AWS_PAGER": ""},
        text=True,
        capture_output=True,
        check=False,
    )


def _run_checked(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd or ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "AWS_PAGER": ""},
        text=True,
        capture_output=True,
        check=False,
    )


def _terragrunt_output_json(module_path: Path, output_name: str) -> object:
    result = _run_checked(
        [
            "terragrunt",
            "output",
            "-json",
            output_name,
            "--non-interactive",
        ],
        cwd=module_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _wait_for_healthy_target(region: str, target_group_arn: str, attempts: int = 20, delay: int = 15) -> None:
    last_output = ""
    for _ in range(attempts):
        result = _run_checked(
            [
                "aws",
                "elbv2",
                "describe-target-health",
                "--region",
                region,
                "--target-group-arn",
                target_group_arn,
                "--output",
                "json",
            ]
        )
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        descriptions = payload.get("TargetHealthDescriptions", [])
        last_output = result.stdout
        if any(
            item.get("TargetHealth", {}).get("State") == "healthy"
            for item in descriptions
        ):
            return
        time.sleep(delay)
    pytest.fail(f"Target group never became healthy: {last_output}")


def _wait_for_registered_instance(
    region: str,
    target_group_arn: str,
    expected_instance_id: str,
    attempts: int = 20,
    delay: int = 15,
) -> None:
    last_output = ""
    for _ in range(attempts):
        result = _run_checked(
            [
                "aws",
                "elbv2",
                "describe-target-health",
                "--region",
                region,
                "--target-group-arn",
                target_group_arn,
                "--output",
                "json",
            ]
        )
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        descriptions = payload.get("TargetHealthDescriptions", [])
        last_output = result.stdout
        if any(
            item.get("Target", {}).get("Id") == expected_instance_id
            for item in descriptions
        ):
            return
        time.sleep(delay)
    pytest.fail(
        f"Expected instance {expected_instance_id} was not registered in target group: {last_output}"
    )


def _assert_alb_http_ready(alb_dns: str, attempts: int = 10, delay: int = 10) -> None:
    last_code = ""
    for _ in range(attempts):
        result = _run_checked(
            [
                "curl",
                "-sS",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                f"http://{alb_dns}/",
            ]
        )
        assert result.returncode == 0, result.stdout + result.stderr
        last_code = result.stdout.strip()
        if last_code in {"200", "302"}:
            return
        time.sleep(delay)
    pytest.fail(f"ALB did not return expected HTTP status, last code={last_code}")


def test_full_stack_smoke_cycle():
    env, region = _require_aws_smoke_env()

    deploy = _run_cli("--env", env, "--region", region, "deploy", "--target", "full")
    try:
        assert deploy.returncode == 0, deploy.stdout + deploy.stderr

        alb_dir = ROOT / "env" / "stack" / "collibra-dq" / "addons" / "collibra-dq-standalone" / "alb"
        standalone_dir = ROOT / "env" / "stack" / "collibra-dq" / "addons" / "collibra-dq-standalone"
        tg_arns = _terragrunt_output_json(alb_dir, "target_group_arns")
        alb_dns = _terragrunt_output_json(alb_dir, "load_balancer_dns_name")
        instance_id = _terragrunt_output_json(standalone_dir, "instance_id")

        target_group_arn = tg_arns["value"]["collibra-dq"]
        _wait_for_registered_instance(region, target_group_arn, instance_id["value"])
        _wait_for_healthy_target(region, target_group_arn)
        _assert_alb_http_ready(alb_dns["value"])
    finally:
        destroy = _run_cli("--env", env, "--region", region, "destroy", "--target", "all", "--yes")
        assert destroy.returncode == 0, destroy.stdout + destroy.stderr
