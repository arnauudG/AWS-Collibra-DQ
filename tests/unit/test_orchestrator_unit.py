from __future__ import annotations

from pathlib import Path

import pytest

from collibra_dq_starter import orchestrator
from collibra_dq_starter.shell import CommandResult


def _res(returncode: int = 0, stdout: str = "", stderr: str = "") -> CommandResult:
    return CommandResult(returncode=returncode, stdout=stdout, stderr=stderr)


def _ctx() -> orchestrator.Context:
    return orchestrator.Context(
        environment="dev",
        region="eu-west-1",
        org="dq",
        aws_account_id="111111111111",
    )


def test_parse_s3_url():
    assert orchestrator._parse_s3_url("s3://bucket/key") == ("bucket", "key")
    assert orchestrator._parse_s3_url("https://example.com/x") is None
    assert orchestrator._parse_s3_url("s3://bucket-only") is None
    assert orchestrator._parse_s3_url("s3:///x") is None


def test_s3_object_exists_checks_head_object(monkeypatch):
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        orchestrator,
        "run",
        lambda command, **_kwargs: commands.append(tuple(command)) or _res(returncode=0),
    )

    assert orchestrator._s3_object_exists("s3://bucket/key") is True
    assert commands == [("aws", "s3api", "head-object", "--bucket", "bucket", "--key", "key")]


def test_table_exists_checks_dynamodb(monkeypatch):
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        orchestrator,
        "run",
        lambda command, **_kwargs: commands.append(tuple(command)) or _res(returncode=0),
    )

    assert orchestrator._table_exists("table", "eu-west-1") is True
    assert commands == [
        ("aws", "dynamodb", "describe-table", "--table-name", "table", "--region", "eu-west-1")
    ]


def test_require_core_env_happy_path(monkeypatch):
    monkeypatch.setenv("TF_VAR_environment", "dev")
    monkeypatch.setenv("TF_VAR_region", "eu-west-1")
    monkeypatch.setenv("TG_ORG", "custom")

    assert orchestrator._require_core_env() == ("dev", "eu-west-1", "custom")


def test_require_core_env_rejects_invalid_region(monkeypatch):
    monkeypatch.setenv("TF_VAR_environment", "dev")
    monkeypatch.setenv("TF_VAR_region", "moon-1")

    with pytest.raises(RuntimeError, match="Invalid TF_VAR_region"):
        orchestrator._require_core_env()


@pytest.mark.parametrize(
    "region",
    ["ap-southeast-2", "us-gov-west-1", "me-south-1", "af-south-1", "sa-east-1"],
)
def test_require_core_env_accepts_valid_aws_regions(monkeypatch, region):
    monkeypatch.setenv("TF_VAR_environment", "dev")
    monkeypatch.setenv("TF_VAR_region", region)
    monkeypatch.setenv("TG_ORG", "dq")

    _, reg, _ = orchestrator._require_core_env()
    assert reg == region


@pytest.mark.parametrize(
    "region",
    ["moon-1", "123-abc-1", "eu_west_1", "EU-WEST-1", "eu-west-"],
)
def test_require_core_env_rejects_malformed_regions(monkeypatch, region):
    monkeypatch.setenv("TF_VAR_environment", "dev")
    monkeypatch.setenv("TF_VAR_region", region)

    with pytest.raises(RuntimeError, match="Invalid TF_VAR_region"):
        orchestrator._require_core_env()


def test_validate_uuid_env_rejects_invalid(monkeypatch):
    monkeypatch.setenv("COLLIBRA_DQ_INSTALLATION_ID", "not-a-uuid")

    with pytest.raises(RuntimeError, match="must be a valid UUID"):
        orchestrator._validate_uuid_env("COLLIBRA_DQ_INSTALLATION_ID")


def test_resolve_account_id_rejects_empty(monkeypatch):
    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: _res(stdout=""))

    with pytest.raises(RuntimeError, match="Unable to resolve AWS account ID"):
        orchestrator._resolve_account_id()


def test_resolve_latest_rhel7_ami_rejects_invalid(monkeypatch):
    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: _res(stdout="None"))
    with pytest.raises(RuntimeError, match="Unable to resolve a valid RHEL 7.9 AMI"):
        orchestrator._resolve_latest_rhel7_ami("eu-west-1")


def test_validate_deploy_target_requires_license(monkeypatch):
    monkeypatch.delenv("COLLIBRA_DQ_LICENSE_KEY", raising=False)
    monkeypatch.setenv("TF_VAR_environment", "dev")
    monkeypatch.setenv("TF_VAR_region", "eu-west-1")
    monkeypatch.setattr(orchestrator, "_require_command", lambda _name: None)

    with pytest.raises(RuntimeError, match="COLLIBRA_DQ_LICENSE_KEY is required"):
        orchestrator._validate_deploy_target("full")


def test_validate_deploy_target_package_requires_local_file(monkeypatch, tmp_path):
    monkeypatch.setenv("TF_VAR_environment", "dev")
    monkeypatch.setenv("TF_VAR_region", "eu-west-1")
    monkeypatch.setattr(orchestrator, "_require_command", lambda _name: None)
    monkeypatch.setattr(orchestrator, "_resolve_account_id", lambda: "111111111111")
    monkeypatch.setattr(orchestrator, "_project_root", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="Local package file not found"):
        orchestrator._validate_deploy_target("package")


def test_discover_project_root_uses_valid_override(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    (root / "env" / "stack" / "collibra-dq").mkdir(parents=True)
    (root / "module" / "application" / "collibra-dq-standalone").mkdir(parents=True)
    (root / "pyproject.toml").write_text("", encoding="utf-8")
    (root / "env" / "stack" / "collibra-dq" / "root.hcl").write_text("", encoding="utf-8")
    monkeypatch.setenv(orchestrator.ROOT_ENV_VAR, str(root))

    assert orchestrator._discover_project_root() == root.resolve()


def test_discover_project_root_rejects_invalid_override(monkeypatch, tmp_path):
    monkeypatch.setenv(orchestrator.ROOT_ENV_VAR, str(tmp_path))

    with pytest.raises(RuntimeError, match="not a valid project root"):
        orchestrator._discover_project_root()


def test_terragrunt_output_exists_uses_state_fallback(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: module_dir)

    calls: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        if command[:2] == ["terragrunt", "output"]:
            return _res(stdout="{}")
        if command[:2] == ["terragrunt", "state"]:
            return _res(stdout="aws_s3_bucket.example")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run", fake_run)

    assert orchestrator._terragrunt_output_exists("x") is True
    assert calls[0][:2] == ("terragrunt", "output")
    assert calls[1][:2] == ("terragrunt", "state")


def test_terragrunt_output_exists_returns_false_on_invalid_json(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: module_dir)
    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: _res(stdout="{nope"))

    assert orchestrator._terragrunt_output_exists("x") is False


def test_terragrunt_import_if_needed_accepts_already_managed(monkeypatch, tmp_path):
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    monkeypatch.setattr(
        orchestrator,
        "run",
        lambda *_args, **_kwargs: _res(returncode=1, stderr="Resource already managed by Terraform"),
    )
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    orchestrator._terragrunt_import_if_needed(bootstrap_dir, "aws_s3_bucket.tfstate", "bucket")


def test_terragrunt_import_if_needed_raises_on_failure(monkeypatch, tmp_path):
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: _res(returncode=1, stderr="boom"))
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    with pytest.raises(orchestrator.CommandError, match="Failed to import"):
        orchestrator._terragrunt_import_if_needed(bootstrap_dir, "aws_s3_bucket.tfstate", "bucket")


def test_terragrunt_apply_retries_after_provider_init_failure(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: module_dir)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    responses = iter(
        [
            _res(returncode=1, stderr="Required plugins are not installed"),
            _res(returncode=0, stdout="init ok"),
            _res(returncode=0, stdout="apply ok"),
        ]
    )
    seen: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        seen.append(tuple(command))
        return next(responses)

    monkeypatch.setattr(orchestrator, "run", fake_run)

    orchestrator._terragrunt_apply("x", "Module")
    assert seen[0][:2] == ("terragrunt", "apply")
    assert seen[1][:2] == ("terragrunt", "init")
    assert seen[2][:2] == ("terragrunt", "apply")


def test_terragrunt_apply_with_extra_env_retries_and_merges(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: module_dir)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    responses = iter(
        [
            _res(returncode=1, stderr="terraform init"),
            _res(returncode=0),
            _res(returncode=0),
        ]
    )
    envs: list[dict[str, str] | None] = []

    def fake_run(_command, **kwargs):
        envs.append(kwargs.get("env"))
        return next(responses)

    monkeypatch.setattr(orchestrator, "run", fake_run)

    orchestrator._terragrunt_apply("x", "Module", extra_env={"EXTRA_FLAG": "1"})
    assert envs[0]["EXTRA_FLAG"] == "1"
    assert envs[0]["TF_INPUT"] == "0"


def test_terragrunt_apply_raises_on_non_retryable_failure(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: module_dir)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)
    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: _res(returncode=1, stderr="hard fail"))

    with pytest.raises(orchestrator.CommandError, match="Failed to deploy Module"):
        orchestrator._terragrunt_apply("x", "Module")


def test_wait_for_bucket_retries_until_present(monkeypatch):
    seen = iter([False, False, True])
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: next(seen))
    monkeypatch.setattr(orchestrator.time, "sleep", lambda _seconds: None)

    assert orchestrator._wait_for_bucket("bucket", max_attempts=3, delay_seconds=0) is True


def test_ensure_shared_artifact_bucket_applies_when_missing(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_artifact_bucket_name", lambda _ctx: "shared-bucket")
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: False)
    monkeypatch.setattr(orchestrator, "_wait_for_bucket", lambda _bucket, **_kwargs: True)

    applied: list[tuple[str, dict[str, str] | None]] = []
    monkeypatch.setattr(
        orchestrator,
        "_terragrunt_apply",
        lambda module_path, _name, extra_env=None: applied.append((module_path, extra_env)),
    )

    orchestrator._ensure_shared_artifact_bucket(ctx)
    assert applied == [("shared/artifact-bucket", {"COLLIBRA_DQ_PACKAGE_LOCAL_PATH": ""})]


def test_ensure_shared_artifact_bucket_raises_when_bucket_never_appears(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_artifact_bucket_name", lambda _ctx: "shared-bucket")
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: False)
    monkeypatch.setattr(orchestrator, "_wait_for_bucket", lambda _bucket, **_kwargs: False)
    monkeypatch.setattr(orchestrator, "_terragrunt_apply", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="Shared artifact bucket not found after deploy"):
        orchestrator._ensure_shared_artifact_bucket(ctx)


def test_ensure_package_artifact_available_skips_http_url(monkeypatch):
    monkeypatch.setenv("COLLIBRA_DQ_PACKAGE_URL", "https://example.com/package.tar")
    monkeypatch.setattr(orchestrator, "_terragrunt_apply", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError))

    orchestrator._ensure_package_artifact_available(_ctx())


def test_ensure_package_artifact_available_uploads_missing_s3_artifact(monkeypatch, tmp_path):
    local_file = tmp_path / orchestrator.DEFAULT_PACKAGE_FILENAME
    local_file.write_text("x", encoding="utf-8")
    monkeypatch.delenv("COLLIBRA_DQ_PACKAGE_URL", raising=False)
    monkeypatch.setattr(orchestrator, "_s3_object_exists", lambda _url: False)
    monkeypatch.setattr(orchestrator, "_local_package_path", lambda: local_file)

    applied: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "_terragrunt_apply",
        lambda module_path, _name: applied.append(module_path),
    )

    orchestrator._ensure_package_artifact_available(_ctx())
    assert applied == [path for path, _ in orchestrator.PACKAGE_DEPLOY_ORDER]


def test_ensure_package_artifact_available_fails_without_s3_or_local(monkeypatch, tmp_path):
    missing = tmp_path / "missing.tar"
    monkeypatch.delenv("COLLIBRA_DQ_PACKAGE_URL", raising=False)
    monkeypatch.setattr(orchestrator, "_s3_object_exists", lambda _url: False)
    monkeypatch.setattr(orchestrator, "_local_package_path", lambda: missing)

    with pytest.raises(RuntimeError, match="Package not found in S3"):
        orchestrator._ensure_package_artifact_available(_ctx())


def test_deploy_bootstrap_imports_existing_resources_when_state_missing(monkeypatch, tmp_path):
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: bootstrap_dir)
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: True)
    monkeypatch.setattr(orchestrator, "_table_exists", lambda _table, _region: True)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    runs: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        runs.append(tuple(command))
        if command[:4] == ["terragrunt", "output", "-json", "state_bucket"]:
            return _res(returncode=1)
        if command[:2] == ["terragrunt", "init"]:
            return _res(returncode=0)
        if command[:2] == ["terragrunt", "apply"]:
            return _res(returncode=0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run", fake_run)
    imports: list[tuple[str, str]] = []
    monkeypatch.setattr(
        orchestrator,
        "_terragrunt_import_if_needed",
        lambda _dir, address, import_id: imports.append((address, import_id)),
    )

    orchestrator.deploy_bootstrap(_ctx())
    assert ("aws_s3_bucket.tfstate", "111111111111-dq-dev-collibra-dq-tfstate-eu-west-1") in imports
    assert ("aws_dynamodb_table.locks", "111111111111-dq-dev-collibra-dq-tf-locks") in imports


def test_deploy_bootstrap_creates_when_resources_absent(monkeypatch, tmp_path):
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: bootstrap_dir)
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: False)
    monkeypatch.setattr(orchestrator, "_table_exists", lambda _table, _region: False)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    commands: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        commands.append(tuple(command))
        if command[:4] == ["terragrunt", "output", "-json", "state_bucket"]:
            return _res(returncode=1)
        if command[:2] == ["terragrunt", "apply"]:
            return _res(returncode=0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run", fake_run)

    orchestrator.deploy_bootstrap(_ctx())
    assert any(cmd[:2] == ("terragrunt", "apply") for cmd in commands)


def test_ensure_install_script_bucket_retries_once(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_install_script_bucket_name", lambda _ctx: "bucket")
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: False)

    wait_results = iter([False, True])
    monkeypatch.setattr(
        orchestrator,
        "_wait_for_bucket",
        lambda _bucket, **_kwargs: next(wait_results),
    )

    apply_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        orchestrator,
        "_terragrunt_apply",
        lambda module_path, module_name: apply_calls.append((module_path, module_name)),
    )

    orchestrator._ensure_install_script_bucket(ctx)
    assert len(apply_calls) == 2


def test_delete_bootstrap_backend_deletes_bucket_and_table(monkeypatch):
    bucket_states = iter([True, False, False])
    table_states = iter([True, False, False])
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: next(bucket_states))
    monkeypatch.setattr(orchestrator, "_table_exists", lambda _table, _region: next(table_states))
    monkeypatch.setattr(orchestrator, "_purge_bucket_versions", lambda _bucket: None)
    monkeypatch.setattr(orchestrator.time, "sleep", lambda _seconds: None)

    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        orchestrator,
        "run",
        lambda command, **_kwargs: commands.append(tuple(command)) or _res(returncode=0),
    )

    orchestrator._delete_bootstrap_backend("bucket", "table", "eu-west-1")
    assert ("aws", "s3api", "delete-bucket", "--bucket", "bucket") in commands
    assert ("aws", "dynamodb", "delete-table", "--table-name", "table", "--region", "eu-west-1") in commands


def test_purge_bucket_versions_handles_truncated_pages(monkeypatch):
    bucket_exists = iter([True])
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: next(bucket_exists))
    delete_calls: list[tuple[str, ...]] = []

    pages = iter(
        [
            _res(
                stdout='{"Versions":[{"Key":"a","VersionId":"1"}],"DeleteMarkers":[],"IsTruncated":true,"NextKeyMarker":"k","NextVersionIdMarker":"v"}'
            ),
            _res(
                stdout='{"Versions":[],"DeleteMarkers":[{"Key":"b","VersionId":"2"}],"IsTruncated":false}'
            ),
        ]
    )

    def fake_run(command, **_kwargs):
        if command[:4] == ["aws", "s3api", "list-object-versions", "--bucket"]:
            return next(pages)
        if command[:4] == ["aws", "s3api", "delete-objects", "--bucket"]:
            delete_calls.append(tuple(command))
            return _res(returncode=0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run", fake_run)

    orchestrator._purge_bucket_versions("bucket")
    assert len(delete_calls) == 2


def test_purge_bucket_versions_returns_on_no_such_bucket(monkeypatch):
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: True)
    monkeypatch.setattr(
        orchestrator,
        "run",
        lambda *_args, **_kwargs: _res(returncode=1, stderr="NoSuchBucket"),
    )

    orchestrator._purge_bucket_versions("bucket")


def test_apply_addon_module_recovers_on_missing_install_script_bucket(monkeypatch):
    ctx = _ctx()
    calls: list[str] = []

    def fake_apply(module_path: str, _module_name: str) -> None:
        calls.append(module_path)
        if len(calls) == 1:
            raise orchestrator.CommandError("NoSuchBucket ... install_collibra_dq.sh")

    ensured: list[bool] = []
    monkeypatch.setattr(orchestrator, "_terragrunt_apply", fake_apply)
    monkeypatch.setattr(orchestrator, "_ensure_install_script_bucket", lambda _ctx: ensured.append(True))

    orchestrator._apply_addon_module("addons/collibra-dq-standalone", "EC2", ctx)
    assert len(ensured) == 1
    assert calls == ["addons/collibra-dq-standalone", "addons/collibra-dq-standalone"]


def test_deploy_full_executes_expected_order(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_validate_deploy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "deploy_bootstrap", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_shared_artifact_bucket", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_package_artifact_available", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_install_script_bucket", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_ami_id_for_addons", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "ok", lambda _msg: None)
    monkeypatch.setattr(orchestrator, "info", lambda _msg: None)

    infra_calls: list[str] = []
    addon_calls: list[str] = []
    monkeypatch.setattr(
        orchestrator, "_terragrunt_apply",
        lambda module_path, _name, extra_env=None: infra_calls.append(module_path),
    )
    monkeypatch.setattr(
        orchestrator,
        "_apply_addon_module",
        lambda module_path, _name, _ctx: addon_calls.append(module_path),
    )

    orchestrator.deploy("full")
    assert infra_calls == [path for path, _ in orchestrator.INFRA_DEPLOY_ORDER]
    assert addon_calls == [path for path, _ in orchestrator.ADDON_DEPLOY_ORDER]


def test_deploy_bootstrap_target_only(monkeypatch):
    ctx = _ctx()
    called: list[bool] = []
    monkeypatch.setattr(orchestrator, "_validate_deploy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "deploy_bootstrap", lambda _ctx: called.append(True))

    orchestrator.deploy("bootstrap")
    assert called == [True]


def test_deploy_addon_runs_only_addon_order(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_validate_deploy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "deploy_bootstrap", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_shared_artifact_bucket", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_package_artifact_available", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_install_script_bucket", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_ami_id_for_addons", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "ok", lambda _msg: None)
    monkeypatch.setattr(orchestrator, "info", lambda _msg: None)

    addon_calls: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "_apply_addon_module",
        lambda module_path, _name, _ctx: addon_calls.append(module_path),
    )

    orchestrator.deploy("addon")
    assert addon_calls == [path for path, _ in orchestrator.ADDON_DEPLOY_ORDER]


def test_deploy_package_only_runs_package_order(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_validate_deploy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "deploy_bootstrap", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_shared_artifact_bucket", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_package_artifact_available", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "ok", lambda _msg: None)
    monkeypatch.setattr(orchestrator, "info", lambda _msg: None)

    applied: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "_terragrunt_apply",
        lambda module_path, _name, extra_env=None: applied.append(module_path),
    )

    orchestrator.deploy("package")
    assert applied == [path for path, _ in orchestrator.PACKAGE_DEPLOY_ORDER]


def test_destroy_stack_preserves_bootstrap(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_validate_destroy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "ok", lambda _msg: None)
    monkeypatch.setattr(orchestrator, "info", lambda _msg: None)

    destroyed: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "_terragrunt_destroy",
        lambda module_path, _name: destroyed.append(module_path),
    )

    bootstrap_called: list[bool] = []
    monkeypatch.setattr(
        orchestrator,
        "destroy_bootstrap",
        lambda *_args, **_kwargs: bootstrap_called.append(True),
    )

    orchestrator.destroy("stack", auto_approve=True)
    assert bootstrap_called == []
    assert destroyed == [
        *(path for path, _ in reversed(orchestrator.ADDON_DEPLOY_ORDER)),
        *(path for path, _ in reversed(orchestrator.INFRA_DEPLOY_ORDER)),
    ]


def test_destroy_package_only_runs_package_destroy(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_validate_destroy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "ok", lambda _msg: None)
    monkeypatch.setattr(orchestrator, "info", lambda _msg: None)

    destroyed: list[str] = []
    monkeypatch.setattr(orchestrator, "_terragrunt_destroy", lambda module_path, _name: destroyed.append(module_path))

    orchestrator.destroy("package", auto_approve=True)
    assert destroyed == [path for path, _ in reversed(orchestrator.PACKAGE_DEPLOY_ORDER)]


def test_destroy_all_executes_expected_reverse_order(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_validate_destroy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "destroy_bootstrap", lambda _ctx, interactive=True: None)
    monkeypatch.setattr(orchestrator, "ok", lambda _msg: None)
    monkeypatch.setattr(orchestrator, "info", lambda _msg: None)

    destroyed: list[str] = []
    monkeypatch.setattr(
        orchestrator,
        "_terragrunt_destroy",
        lambda module_path, _name: destroyed.append(module_path),
    )

    orchestrator.destroy("all", auto_approve=True)
    expected = [
        *(path for path, _ in reversed(orchestrator.ADDON_DEPLOY_ORDER)),
        *(path for path, _ in reversed(orchestrator.INFRA_DEPLOY_ORDER)),
        *(path for path, _ in reversed(orchestrator.PACKAGE_DEPLOY_ORDER)),
        *(path for path, _ in reversed(orchestrator.SHARED_DEPLOY_ORDER)),
    ]
    assert destroyed == expected


# ---------------------------------------------------------------------------
# Stage-based parallel execution tests
# ---------------------------------------------------------------------------


def test_addon_stages_flatten_to_addon_deploy_order():
    flat = [m for stage in orchestrator.ADDON_STAGES for m in stage]
    assert flat == orchestrator.ADDON_DEPLOY_ORDER


def test_run_stage_sequential_executes_in_order():
    modules = [("a", "Module A"), ("b", "Module B"), ("c", "Module C")]
    calls: list[str] = []
    orchestrator._run_stage(modules, lambda mp, _mn: calls.append(mp), parallel=False)
    assert calls == ["a", "b", "c"]


def test_run_stage_parallel_runs_all_modules():
    modules = [("a", "Module A"), ("b", "Module B")]
    calls: list[str] = []

    def fake_apply(mp, _mn):
        calls.append(mp)

    orchestrator._run_stage(modules, fake_apply, parallel=True)
    assert sorted(calls) == ["a", "b"]


def test_run_stage_parallel_collects_errors():
    modules = [("a", "Module A"), ("b", "Module B")]

    def failing_apply(mp, _mn):
        if mp == "b":
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        orchestrator._run_stage(modules, failing_apply, parallel=True)


def test_run_stage_single_module_skips_threadpool():
    """A stage with 1 module runs sequentially even when parallel=True."""
    modules = [("a", "Module A")]
    calls: list[str] = []
    orchestrator._run_stage(modules, lambda mp, _mn: calls.append(mp), parallel=True)
    assert calls == ["a"]


def test_deploy_full_parallel_flag_propagates(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_validate_deploy_target", lambda _target: ctx)
    monkeypatch.setattr(orchestrator, "deploy_bootstrap", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_shared_artifact_bucket", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_package_artifact_available", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_install_script_bucket", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "_ensure_ami_id_for_addons", lambda _ctx: None)
    monkeypatch.setattr(orchestrator, "ok", lambda _msg: None)
    monkeypatch.setattr(orchestrator, "info", lambda _msg: None)
    monkeypatch.setattr(
        orchestrator, "_terragrunt_apply",
        lambda module_path, _name, extra_env=None: None,
    )

    parallel_values: list[bool] = []
    original = orchestrator._deploy_addon_stages

    def capture_parallel(ctx, *, parallel=False):
        parallel_values.append(parallel)
        monkeypatch.setattr(
            orchestrator, "_apply_addon_module",
            lambda module_path, _name, _ctx: None,
        )
        return original(ctx, parallel=False)

    monkeypatch.setattr(orchestrator, "_deploy_addon_stages", capture_parallel)

    orchestrator.deploy("full", parallel=True)
    assert parallel_values == [True]


def test_deploy_addon_stages_calls_apply_addon_module(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(orchestrator, "_ensure_install_script_bucket", lambda _ctx: None)

    calls: list[str] = []
    monkeypatch.setattr(
        orchestrator, "_apply_addon_module",
        lambda mp, _mn, _ctx: calls.append(mp),
    )

    orchestrator._deploy_addon_stages(ctx, parallel=False)
    assert calls == [path for path, _ in orchestrator.ADDON_DEPLOY_ORDER]


def test_destroy_addon_stages_calls_terragrunt_destroy(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        orchestrator, "_terragrunt_destroy",
        lambda mp, _mn: calls.append(mp),
    )

    orchestrator._destroy_addon_stages(parallel=False)
    assert calls == [path for path, _ in reversed(orchestrator.ADDON_DEPLOY_ORDER)]
