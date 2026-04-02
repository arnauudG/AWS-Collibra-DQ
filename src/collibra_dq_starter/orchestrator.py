from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .shell import CommandError, CommandResult, run

DeployTarget = Literal["bootstrap", "stack", "addon", "package", "full"]
DestroyTarget = Literal["addon", "stack", "package", "all"]

STACK = "collibra-dq"

ALLOWED_ENVS = {"dev", "prod"}
ALLOWED_REGIONS = {"eu-west-1", "us-east-1", "eu-central-1"}

NON_INTERACTIVE_ENV = {"TF_INPUT": "0", "TG_INPUT": "0"}

SHARED_DEPLOY_ORDER = [
    ("shared/artifact-bucket", "Shared Artifact Bucket"),
]

INFRA_DEPLOY_ORDER = [
    ("network/vpc", "VPC"),
    ("network/vpc-endpoints", "VPC Endpoints"),
]

ADDON_DEPLOY_ORDER = [
    ("addons/collibra-dq-standalone/install-script-bucket", "Install Script Bucket"),
    ("addons/collibra-dq-standalone/alb/sg-alb", "ALB Security Group"),
    ("addons/collibra-dq-standalone/sg-collibra-dq", "Collibra DQ Security Group"),
    ("database/rds-collibra-dq/sg-rds", "RDS Security Group"),
    ("database/rds-collibra-dq/rds", "RDS PostgreSQL Database"),
    ("addons/collibra-dq-standalone", "Collibra DQ EC2 Instance"),
    ("addons/collibra-dq-standalone/rotation-restart", "RDS Rotation Restart Hook"),
    ("addons/collibra-dq-standalone/alb", "Application Load Balancer"),
    ("addons/collibra-dq-standalone/alb/target-group-attachment", "Target Group Attachment"),
]

PACKAGE_DEPLOY_ORDER = [
    ("addons/collibra-dq-standalone/package-upload", "Package Upload (S3)"),
]

ROOT_ENV_VAR = "COLLIBRA_DQ_STARTER_ROOT"
DEFAULT_PACKAGE_FILENAME = "dq-2025.11-SPARK356-JDK17-package-full.tar"
_PROJECT_ROOT_CACHE: Path | None = None


@dataclass(frozen=True)
class Context:
    environment: str
    region: str
    org: str
    aws_account_id: str


def _discover_project_root() -> Path:
    def is_project_root(candidate: Path) -> bool:
        return (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "env" / "stack" / "collibra-dq" / "root.hcl").is_file()
            and (candidate / "module" / "application" / "collibra-dq-standalone").is_dir()
        )

    override = os.environ.get(ROOT_ENV_VAR, "").strip()
    if override:
        candidate = Path(override).expanduser().resolve()
        if is_project_root(candidate):
            return candidate
        raise RuntimeError(
            f"{ROOT_ENV_VAR} is set to {candidate}, but it is not a valid project root."
        )

    search_roots = [Path.cwd().resolve(), *Path.cwd().resolve().parents]
    module_path = Path(__file__).resolve()
    search_roots.extend(module_path.parents)

    for root in search_roots:
        if is_project_root(root):
            return root

    raise RuntimeError(
        "Unable to locate project root. Run from the repository directory or set "
        f"{ROOT_ENV_VAR} to the project root."
    )


def _project_root() -> Path:
    global _PROJECT_ROOT_CACHE
    if _PROJECT_ROOT_CACHE is None:
        _PROJECT_ROOT_CACHE = _discover_project_root()
    return _PROJECT_ROOT_CACHE


def _echo(level: str, color: str, message: str) -> None:
    reset = "\033[0m"
    print(f"{color}[{level}]{reset} {message}")


def info(message: str) -> None:
    _echo("INFO", "\033[0;34m", message)


def ok(message: str) -> None:
    _echo("OK", "\033[0;32m", message)


def warn(message: str) -> None:
    _echo("WARNING", "\033[1;33m", message)


def _print_result_output(result: CommandResult) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")


def _require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required command not found: {name}")


def _require_core_env() -> tuple[str, str, str]:
    environment = os.environ.get("TF_VAR_environment", "").strip()
    region = os.environ.get("TF_VAR_region", "").strip()
    org = os.environ.get("TG_ORG", "dq").strip() or "dq"

    if not environment or not region:
        raise RuntimeError("TF_VAR_environment and TF_VAR_region must be set.")
    if environment not in ALLOWED_ENVS:
        raise RuntimeError(
            f"Invalid TF_VAR_environment: {environment} (allowed: dev|prod)"
        )
    if region not in ALLOWED_REGIONS:
        raise RuntimeError(
            "Invalid TF_VAR_region: "
            f"{region} (allowed: eu-west-1|us-east-1|eu-central-1)"
        )
    return environment, region, org


def _resolve_account_id() -> str:
    result = run(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        check=True,
    )
    account = result.stdout.strip()
    if not account:
        raise RuntimeError("Unable to resolve AWS account ID from current credentials.")
    return account


def _validate_uuid_env(var_name: str) -> None:
    value = os.environ.get(var_name, "").strip()
    if not value:
        return
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise RuntimeError(
            f"{var_name} must be a valid UUID when set (got: {value!r})."
        ) from exc


def _validate_deploy_target(target: DeployTarget) -> Context:
    _require_command("aws")
    _require_command("terragrunt")
    if target in {"stack", "addon", "package", "full"}:
        _require_command("terraform")

    if target in {"addon", "full"}:
        license_key = os.environ.get("COLLIBRA_DQ_LICENSE_KEY", "").strip()
        if not license_key:
            raise RuntimeError(
                f"COLLIBRA_DQ_LICENSE_KEY is required for deploy --target {target}."
            )
        _validate_uuid_env("COLLIBRA_DQ_INSTALLATION_ID")
    elif target == "package":
        package_filename = (
            os.environ.get("COLLIBRA_DQ_PACKAGE_FILENAME", DEFAULT_PACKAGE_FILENAME).strip()
            or DEFAULT_PACKAGE_FILENAME
        )
        package_path = _project_root() / "packages" / "collibra-dq" / package_filename
        if not package_path.is_file():
            raise RuntimeError(
                "Local package file not found for deploy --target package: "
                f"{package_path}\n"
                "Place the file in packages/collibra-dq/ or set COLLIBRA_DQ_PACKAGE_FILENAME."
            )

    environment, region, org = _require_core_env()
    account = _resolve_account_id()
    return Context(environment=environment, region=region, org=org, aws_account_id=account)


def _resolve_latest_rhel7_ami(region: str) -> str:
    result = run(
        [
            "aws",
            "ec2",
            "describe-images",
            "--region",
            region,
            "--owners",
            "309956199498",
            "--filters",
            "Name=name,Values=RHEL-7.9*HVM*",
            "Name=architecture,Values=x86_64",
            "Name=root-device-type,Values=ebs",
            "Name=state,Values=available",
            "--query",
            "sort_by(Images,&CreationDate)[-1].ImageId",
            "--output",
            "text",
        ],
        check=True,
    )
    ami_id = result.stdout.strip()
    if not ami_id or ami_id == "None" or not ami_id.startswith("ami-"):
        raise RuntimeError(
            f"Unable to resolve a valid RHEL 7.9 AMI in region {region}. "
            "Set COLLIBRA_DQ_AMI_ID explicitly and retry."
        )
    return ami_id


def _ensure_ami_id_for_addons(ctx: Context) -> None:
    if os.environ.get("COLLIBRA_DQ_AMI_ID", "").strip():
        return
    ami_id = _resolve_latest_rhel7_ami(ctx.region)
    os.environ["COLLIBRA_DQ_AMI_ID"] = ami_id
    info(f"Resolved COLLIBRA_DQ_AMI_ID={ami_id} for region {ctx.region}.")


def _validate_destroy_target(_: DestroyTarget) -> Context:
    _require_command("aws")
    _require_command("terragrunt")
    environment, region, org = _require_core_env()
    account = _resolve_account_id()
    return Context(environment=environment, region=region, org=org, aws_account_id=account)


def _module_dir(module_path: str) -> Path:
    return _project_root() / "env" / "stack" / "collibra-dq" / module_path


def _bucket_exists(bucket: str) -> bool:
    return run(["aws", "s3api", "head-bucket", "--bucket", bucket], check=False).returncode == 0


def _parse_s3_url(url: str) -> tuple[str, str] | None:
    if not url.startswith("s3://"):
        return None
    without_scheme = url[len("s3://") :]
    if "/" not in without_scheme:
        return None
    bucket, key = without_scheme.split("/", 1)
    if not bucket or not key:
        return None
    return bucket, key


def _s3_object_exists(s3_url: str) -> bool:
    parsed = _parse_s3_url(s3_url)
    if not parsed:
        return False
    bucket, key = parsed
    return (
        run(
            ["aws", "s3api", "head-object", "--bucket", bucket, "--key", key],
            check=False,
        ).returncode
        == 0
    )


def _table_exists(table: str, region: str) -> bool:
    return (
        run(
            [
                "aws",
                "dynamodb",
                "describe-table",
                "--table-name",
                table,
                "--region",
                region,
            ],
            check=False,
        ).returncode
        == 0
    )


def _purge_bucket_versions(bucket: str) -> None:
    if not _bucket_exists(bucket):
        return

    info(f"Purging all objects/versions from S3 bucket {bucket} before destroy.")
    key_marker = ""
    version_marker = ""

    while True:
        cmd = ["aws", "s3api", "list-object-versions", "--bucket", bucket, "--output", "json"]
        if key_marker:
            cmd.extend(["--key-marker", key_marker])
        if version_marker:
            cmd.extend(["--version-id-marker", version_marker])

        page = run(cmd, check=False)
        if page.returncode != 0:
            if "NoSuchBucket" in page.stderr:
                return
            raise RuntimeError(
                f"Failed to list object versions for bucket {bucket}: {page.stderr or page.stdout}"
            )

        payload = json.loads(page.stdout or "{}")
        objects = []
        for item in payload.get("Versions", []):
            objects.append({"Key": item["Key"], "VersionId": item["VersionId"]})
        for item in payload.get("DeleteMarkers", []):
            objects.append({"Key": item["Key"], "VersionId": item["VersionId"]})

        if objects:
            for idx in range(0, len(objects), 1000):
                batch = objects[idx : idx + 1000]
                run(
                    [
                        "aws",
                        "s3api",
                        "delete-objects",
                        "--bucket",
                        bucket,
                        "--delete",
                        json.dumps({"Objects": batch, "Quiet": True}),
                    ],
                    check=True,
                )

        if not payload.get("IsTruncated", False):
            break
        key_marker = payload.get("NextKeyMarker", "")
        version_marker = payload.get("NextVersionIdMarker", "")


def _clear_state_digest(table: str, bucket: str, key: str, region: str) -> None:
    # Terraform stores backend digest rows as "<bucket>/<key>-md5" in LockID.
    digest_lock_id = f"{bucket}/{key}-md5"
    run(
        [
            "aws",
            "dynamodb",
            "delete-item",
            "--table-name",
            table,
            "--region",
            region,
            "--key",
            json.dumps({"LockID": {"S": digest_lock_id}}),
        ],
        check=False,
    )


def _delete_bootstrap_backend(bucket: str, table: str, region: str) -> None:
    # State-independent cleanup path for broken/missing bootstrap state.
    if _bucket_exists(bucket):
        _purge_bucket_versions(bucket)
        run(["aws", "s3api", "delete-bucket", "--bucket", bucket], check=False)
        for _ in range(12):
            if not _bucket_exists(bucket):
                break
            time.sleep(2)
        if _bucket_exists(bucket):
            raise RuntimeError(f"Failed to delete bootstrap S3 bucket: {bucket}")

    if _table_exists(table, region):
        run(
            [
                "aws",
                "dynamodb",
                "delete-table",
                "--table-name",
                table,
                "--region",
                region,
            ],
            check=False,
        )
        for _ in range(12):
            if not _table_exists(table, region):
                break
            time.sleep(2)
        if _table_exists(table, region):
            raise RuntimeError(f"Failed to delete bootstrap lock table: {table}")


def _terragrunt_import_if_needed(
    bootstrap_dir: Path,
    address: str,
    import_id: str,
) -> None:
    result = run(
        ["terragrunt", "import", address, import_id],
        cwd=bootstrap_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    )
    _print_result_output(result)
    if result.returncode == 0:
        return
    combined = f"{result.stdout}\n{result.stderr}"
    if "Resource already managed by Terraform" in combined:
        info(f"{address} is already tracked in state; skipping import.")
        return
    raise CommandError(f"Failed to import {address} ({import_id}).")


def _terragrunt_output_exists(module_path: str) -> bool:
    module_dir = _module_dir(module_path)
    if not module_dir.is_dir():
        return False
    result = run(
        ["terragrunt", "output", "-json"],
        cwd=module_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    )
    if result.returncode != 0:
        return False
    payload = result.stdout.strip()
    if not payload or payload == "{}":
        # Some modules intentionally have no outputs. Fall back to state listing
        # to decide whether resources exist and destroy should run.
        state = run(
            ["terragrunt", "state", "list"],
            cwd=module_dir,
            check=False,
            env=NON_INTERACTIVE_ENV,
        )
        if state.returncode != 0:
            return False
        return bool(state.stdout.strip())
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return False
    return bool(decoded)


def _terragrunt_apply(module_path: str, module_name: str) -> None:
    module_dir = _module_dir(module_path)
    if not module_dir.is_dir():
        raise RuntimeError(f"Module directory not found: {module_dir}")

    info(f"Deploying {module_name}...")
    apply_result = run(
        ["terragrunt", "apply", "--auto-approve", "--non-interactive"],
        cwd=module_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    )
    _print_result_output(apply_result)
    if apply_result.returncode == 0:
        ok(f"{module_name} deployed.")
        return

    combined = f"{apply_result.stdout}\n{apply_result.stderr}"
    retryable = (
        "Required plugins are not installed" in combined
        or "terraform init" in combined
    )
    if not retryable:
        raise CommandError(f"Failed to deploy {module_name}.\n{combined}")

    warn(f"{module_name}: provider init required, retrying with terragrunt init -upgrade.")
    init_result = run(
        ["terragrunt", "init", "-upgrade", "--non-interactive"],
        cwd=module_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    )
    _print_result_output(init_result)
    retry_result = run(
        ["terragrunt", "apply", "--auto-approve", "--non-interactive"],
        cwd=module_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    )
    _print_result_output(retry_result)
    if retry_result.returncode != 0:
        combined_retry = f"{retry_result.stdout}\n{retry_result.stderr}"
        raise CommandError(f"Failed to deploy {module_name} after init retry.\n{combined_retry}")
    ok(f"{module_name} deployed.")


def _terragrunt_apply_with_env(module_path: str, module_name: str, extra_env: dict[str, str]) -> None:
    module_dir = _module_dir(module_path)
    if not module_dir.is_dir():
        raise RuntimeError(f"Module directory not found: {module_dir}")

    info(f"Deploying {module_name}...")
    env = {**NON_INTERACTIVE_ENV, **extra_env}
    apply_result = run(
        ["terragrunt", "apply", "--auto-approve", "--non-interactive"],
        cwd=module_dir,
        check=False,
        env=env,
    )
    _print_result_output(apply_result)
    if apply_result.returncode == 0:
        ok(f"{module_name} deployed.")
        return

    combined = f"{apply_result.stdout}\n{apply_result.stderr}"
    retryable = (
        "Required plugins are not installed" in combined
        or "terraform init" in combined
    )
    if not retryable:
        raise CommandError(f"Failed to deploy {module_name}.\n{combined}")

    warn(f"{module_name}: provider init required, retrying with terragrunt init -upgrade.")
    init_result = run(
        ["terragrunt", "init", "-upgrade", "--non-interactive"],
        cwd=module_dir,
        check=False,
        env=env,
    )
    _print_result_output(init_result)
    retry_result = run(
        ["terragrunt", "apply", "--auto-approve", "--non-interactive"],
        cwd=module_dir,
        check=False,
        env=env,
    )
    _print_result_output(retry_result)
    if retry_result.returncode != 0:
        combined_retry = f"{retry_result.stdout}\n{retry_result.stderr}"
        raise CommandError(f"Failed to deploy {module_name} after init retry.\n{combined_retry}")
    ok(f"{module_name} deployed.")


def _apply_addon_module(module_path: str, module_name: str, ctx: Context) -> None:
    try:
        _terragrunt_apply(module_path, module_name)
    except CommandError as exc:
        # Defensive recovery: if install-script upload hits NoSuchBucket,
        # recreate/verify package bucket and retry the EC2 module once.
        if (
            module_path == "addons/collibra-dq-standalone"
            and "NoSuchBucket" in str(exc)
            and "install_collibra_dq.sh" in str(exc)
        ):
            warn(
                "Detected missing install-script bucket during EC2 deploy. "
                "Re-applying install-script bucket and retrying EC2 once."
            )
            _ensure_install_script_bucket(ctx)
            _terragrunt_apply(module_path, module_name)
            return
        raise


def _terragrunt_destroy(module_path: str, module_name: str) -> None:
    module_dir = _module_dir(module_path)
    if not _terragrunt_output_exists(module_path):
        warn(f"{module_name} not found, skipping.")
        return
    info(f"Destroying {module_name}...")
    result = run(
        ["terragrunt", "destroy", "--auto-approve", "--non-interactive"],
        cwd=module_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    )
    _print_result_output(result)
    if result.returncode != 0:
        combined = f"{result.stdout}\n{result.stderr}"
        if "BucketNotEmpty" in combined:
            bucket_match = re.search(r"deleting S3 Bucket \(([^)]+)\)", combined)
            if bucket_match:
                bucket = bucket_match.group(1).strip()
                warn(
                    f"{module_name}: bucket {bucket} is versioned/non-empty; "
                    "purging object versions and retrying destroy once."
                )
                _purge_bucket_versions(bucket)
                retry = run(
                    ["terragrunt", "destroy", "--auto-approve", "--non-interactive"],
                    cwd=module_dir,
                    check=False,
                    env=NON_INTERACTIVE_ENV,
                )
                _print_result_output(retry)
                if retry.returncode == 0:
                    ok(f"{module_name} destroyed.")
                    return
                raise CommandError(f"Failed to destroy {module_name} after bucket purge retry.")
        raise CommandError(f"Failed to destroy {module_name}.")
    ok(f"{module_name} destroyed.")


def _artifact_bucket_name(ctx: Context) -> str:
    """Shared artifact bucket (env-independent): holds DQ packages uploaded once."""
    return f"{ctx.aws_account_id}-{ctx.org}-collibra-dq-artifacts-{ctx.region}"


def _install_script_bucket_name(ctx: Context) -> str:
    """Per-env bucket for install script (contains rendered env-specific secrets)."""
    return f"{ctx.aws_account_id}-{ctx.org}-{ctx.environment}-collibra-dq-packages-{ctx.region}"


def _wait_for_bucket(bucket: str, *, max_attempts: int = 10, delay_seconds: float = 2.0) -> bool:
    for _ in range(max_attempts):
        if _bucket_exists(bucket):
            return True
        time.sleep(delay_seconds)
    return _bucket_exists(bucket)


def _ensure_shared_artifact_bucket(ctx: Context) -> None:
    """Deploy the shared artifact bucket (env-independent, created once)."""
    bucket = _artifact_bucket_name(ctx)
    if _bucket_exists(bucket):
        return
    for module_path, module_name in SHARED_DEPLOY_ORDER:
        _terragrunt_apply_with_env(
            module_path,
            module_name,
            {"COLLIBRA_DQ_PACKAGE_LOCAL_PATH": ""},
        )
    if not _wait_for_bucket(bucket, max_attempts=10, delay_seconds=2.0):
        raise RuntimeError(
            f"Shared artifact bucket not found after deploy: {bucket}"
        )


def _ensure_install_script_bucket(ctx: Context) -> None:
    """Deploy the per-env install-script bucket (holds rendered install script)."""
    bucket = _install_script_bucket_name(ctx)
    if _bucket_exists(bucket):
        return
    _terragrunt_apply(
        "addons/collibra-dq-standalone/install-script-bucket",
        "Install Script Bucket (S3)",
    )
    if _wait_for_bucket(bucket, max_attempts=10, delay_seconds=2.0):
        return

    warn(
        f"Install script bucket {bucket} is still missing after apply; retrying once."
    )
    _terragrunt_apply(
        "addons/collibra-dq-standalone/install-script-bucket",
        "Install Script Bucket (S3)",
    )
    if not _wait_for_bucket(bucket, max_attempts=10, delay_seconds=2.0):
        raise RuntimeError(
            "Install script bucket not found after retry. "
            f"Expected bucket: {bucket}"
        )


def _local_package_path() -> Path:
    filename = (
        os.environ.get("COLLIBRA_DQ_PACKAGE_FILENAME", DEFAULT_PACKAGE_FILENAME).strip()
        or DEFAULT_PACKAGE_FILENAME
    )
    return _project_root() / "packages" / "collibra-dq" / filename



def _artifact_s3_url(ctx: Context) -> str:
    """Construct the expected S3 URL for the package in the shared artifact bucket."""
    filename = (
        os.environ.get("COLLIBRA_DQ_PACKAGE_FILENAME", DEFAULT_PACKAGE_FILENAME).strip()
        or DEFAULT_PACKAGE_FILENAME
    )
    return f"s3://{_artifact_bucket_name(ctx)}/collibra-dq/{filename}"


def _ensure_package_artifact_available(ctx: Context) -> None:
    package_url = os.environ.get("COLLIBRA_DQ_PACKAGE_URL", "").strip()

    # If no explicit URL, derive from the shared artifact bucket
    if not package_url:
        package_url = _artifact_s3_url(ctx)

    # For HTTP URLs we cannot reliably validate existence here; trust caller-provided URL.
    if not package_url.startswith("s3://"):
        return
    if _s3_object_exists(package_url):
        return

    warn(
        f"Package not found at {package_url}; "
        "attempting local package upload to shared artifact bucket."
    )

    local_path = _local_package_path()
    if not local_path.is_file():
        raise RuntimeError(
            f"Package not found in S3 ({package_url}) and local file not found for auto-upload: "
            f"{local_path}\n"
            "Place the package file in packages/collibra-dq/ or set COLLIBRA_DQ_PACKAGE_URL."
        )

    info(f"Uploading package artifact from local file: {local_path.name}")
    for module_path, module_name in PACKAGE_DEPLOY_ORDER:
        _terragrunt_apply(module_path, module_name)
    info("Package artifact uploaded to shared artifact bucket.")


def _bootstrap_bucket_name(ctx: Context) -> str:
    return f"{ctx.aws_account_id}-{ctx.org}-{ctx.environment}-{STACK}-tfstate-{ctx.region}"


def _bootstrap_table_name(ctx: Context) -> str:
    return f"{ctx.aws_account_id}-{ctx.org}-{ctx.environment}-{STACK}-tf-locks"


def deploy_bootstrap(ctx: Context) -> None:
    bootstrap_dir = _module_dir("bootstrap")
    if not bootstrap_dir.is_dir():
        raise RuntimeError(f"Bootstrap directory not found: {bootstrap_dir}")

    bucket = _bootstrap_bucket_name(ctx)
    table = _bootstrap_table_name(ctx)

    info("Bootstrapping remote state backend.")
    info(f"Environment={ctx.environment} Region={ctx.region} Account={ctx.aws_account_id}")
    info(f"S3 bucket: {bucket}")
    info(f"DynamoDB table: {table}")

    state_exists = run(
        ["terragrunt", "output", "-json", "state_bucket", "--non-interactive"],
        cwd=bootstrap_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    ).returncode == 0

    if state_exists:
        info("Bootstrap state detected; applying (expected no-op if up to date).")
        result = run(
            ["terragrunt", "apply", "--auto-approve", "--non-interactive"],
            cwd=bootstrap_dir,
            check=True,
            env=NON_INTERACTIVE_ENV,
        )
        _print_result_output(result)
        ok("Bootstrap completed.")
        return

    bucket_exists = _bucket_exists(bucket)
    table_exists = _table_exists(table, ctx.region)

    if bucket_exists and table_exists:
        warn("Bootstrap resources exist but state is missing; importing resources first.")
        run(
            ["terragrunt", "init", "-upgrade", "--non-interactive"],
            cwd=bootstrap_dir,
            check=False,
            env=NON_INTERACTIVE_ENV,
        )
        _terragrunt_import_if_needed(bootstrap_dir, "aws_s3_bucket.tfstate", bucket)
        _terragrunt_import_if_needed(bootstrap_dir, "aws_dynamodb_table.locks", table)
        result = run(
            ["terragrunt", "apply", "--auto-approve", "--non-interactive"],
            cwd=bootstrap_dir,
            check=True,
            env=NON_INTERACTIVE_ENV,
        )
        _print_result_output(result)
        ok("Bootstrap imported and completed.")
        return

    info("Bootstrap resources not found; creating.")
    result = run(
        ["terragrunt", "apply", "--auto-approve", "--non-interactive"],
        cwd=bootstrap_dir,
        check=True,
        env=NON_INTERACTIVE_ENV,
    )
    _print_result_output(result)
    ok("Bootstrap created and completed.")


def destroy_bootstrap(ctx: Context, *, interactive: bool = True) -> None:
    bootstrap_dir = _module_dir("bootstrap")
    if not bootstrap_dir.is_dir():
        raise RuntimeError(f"Bootstrap directory not found: {bootstrap_dir}")

    bucket = _bootstrap_bucket_name(ctx)
    table = _bootstrap_table_name(ctx)

    warn("BOOTSTRAP DESTRUCTION WARNING")
    warn(f"Environment={ctx.environment} Region={ctx.region} Account={ctx.aws_account_id}")
    warn(f"S3 bucket: {bucket}")
    warn(f"DynamoDB table: {table}")

    if interactive:
        answer = input("Type 'DESTROY BOOTSTRAP' to confirm: ").strip()
        if answer != "DESTROY BOOTSTRAP":
            info("Cancelled.")
            return

    state_exists = run(
        ["terragrunt", "output", "-json", "state_bucket", "--non-interactive"],
        cwd=bootstrap_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    ).returncode == 0

    if not state_exists and _bucket_exists(bucket) and _table_exists(table, ctx.region):
        warn(
            "Bootstrap resources exist but state is unreadable/missing. "
            "Using direct backend cleanup path."
        )
        _clear_state_digest(table, bucket, "bootstrap/terraform.tfstate", ctx.region)
        _delete_bootstrap_backend(bucket, table, ctx.region)
        ok("Bootstrap destroyed.")
        return

    result = run(
        ["terragrunt", "destroy", "--auto-approve", "--non-interactive"],
        cwd=bootstrap_dir,
        check=False,
        env=NON_INTERACTIVE_ENV,
    )
    _print_result_output(result)
    if result.returncode != 0:
        # Terragrunt/Terraform can fail after successfully deleting backend resources
        # because it tries to persist final state to the just-deleted S3 backend.
        if not _bucket_exists(bucket) and not _table_exists(table, ctx.region):
            warn(
                "Bootstrap backend resources are already deleted; ignoring "
                "post-destroy backend state persistence errors."
            )
            ok("Bootstrap destroyed.")
            return

        combined = f"{result.stdout}\n{result.stderr}"
        if "state data in S3 does not have the expected content" in combined:
            warn(
                "Detected S3/DynamoDB state digest drift for bootstrap. "
                "Clearing digest row and retrying once."
            )
            _clear_state_digest(table, bucket, "bootstrap/terraform.tfstate", ctx.region)
            time.sleep(3)
            retry = run(
                ["terragrunt", "destroy", "--auto-approve", "--non-interactive"],
                cwd=bootstrap_dir,
                check=False,
                env=NON_INTERACTIVE_ENV,
            )
            _print_result_output(retry)
            if retry.returncode == 0:
                ok("Bootstrap destroyed.")
                return

            if not _bucket_exists(bucket) and not _table_exists(table, ctx.region):
                warn(
                    "Bootstrap backend resources are already deleted; ignoring "
                    "post-destroy backend state persistence errors."
                )
                ok("Bootstrap destroyed.")
                return

            raise CommandError("Failed to destroy bootstrap resources after digest retry.")
        raise CommandError("Failed to destroy bootstrap resources.")

    if result.returncode == 0:
        ok("Bootstrap destroyed.")
        return


def deploy(target: DeployTarget) -> None:
    ctx = _validate_deploy_target(target)
    info(
        f"Deploy target={target} env={ctx.environment} region={ctx.region} account={ctx.aws_account_id}"
    )

    if target == "bootstrap":
        deploy_bootstrap(ctx)
        return

    deploy_bootstrap(ctx)
    _ensure_shared_artifact_bucket(ctx)

    if target == "addon":
        _ensure_package_artifact_available(ctx)
        _ensure_install_script_bucket(ctx)
        _ensure_ami_id_for_addons(ctx)
        for module_path, module_name in ADDON_DEPLOY_ORDER:
            if module_path == "addons/collibra-dq-standalone":
                _ensure_install_script_bucket(ctx)
            _apply_addon_module(module_path, module_name, ctx)
        ok("Deploy completed.")
        return

    if target == "package":
        _ensure_package_artifact_available(ctx)
        for module_path, module_name in PACKAGE_DEPLOY_ORDER:
            _terragrunt_apply(module_path, module_name)
        ok("Deploy completed.")
        return

    for module_path, module_name in INFRA_DEPLOY_ORDER:
        _terragrunt_apply(module_path, module_name)

    if target == "full":
        _ensure_package_artifact_available(ctx)
        _ensure_install_script_bucket(ctx)
        _ensure_ami_id_for_addons(ctx)
        for module_path, module_name in ADDON_DEPLOY_ORDER:
            if module_path == "addons/collibra-dq-standalone":
                _ensure_install_script_bucket(ctx)
            _apply_addon_module(module_path, module_name, ctx)

    ok("Deploy completed.")


def destroy(target: DestroyTarget, *, auto_approve: bool = False) -> None:
    ctx = _validate_destroy_target(target)
    info(
        f"Destroy target={target} env={ctx.environment} region={ctx.region} account={ctx.aws_account_id}"
    )

    if target in {"stack", "all"} and not auto_approve:
        answer = input(f"Destroy target '{target}' in {ctx.environment}/{ctx.region}? (yes/no): ")
        if answer.strip().lower() != "yes":
            info("Cancelled.")
            return

    if target == "package":
        for module_path, module_name in reversed(PACKAGE_DEPLOY_ORDER):
            _terragrunt_destroy(module_path, module_name)
        ok("Destroy completed.")
        return

    if target == "addon":
        for module_path, module_name in reversed(ADDON_DEPLOY_ORDER):
            _terragrunt_destroy(module_path, module_name)
        ok("Destroy completed.")
        return

    for module_path, module_name in reversed(ADDON_DEPLOY_ORDER):
        _terragrunt_destroy(module_path, module_name)
    for module_path, module_name in reversed(INFRA_DEPLOY_ORDER):
        _terragrunt_destroy(module_path, module_name)
    if target == "all":
        for module_path, module_name in reversed(PACKAGE_DEPLOY_ORDER):
            _terragrunt_destroy(module_path, module_name)
        for module_path, module_name in reversed(SHARED_DEPLOY_ORDER):
            _terragrunt_destroy(module_path, module_name)

    if target == "all":
        destroy_bootstrap(ctx, interactive=not auto_approve)
    else:
        info("Bootstrap and shared artifact bucket preserved (use destroy --target all to remove them).")

    ok("Destroy completed.")
