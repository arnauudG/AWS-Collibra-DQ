from __future__ import annotations

import subprocess
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


def test_destroy_retries_bucket_not_empty(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: module_dir)
    monkeypatch.setattr(orchestrator, "_terragrunt_output_exists", lambda _module_path: True)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    runs = iter(
        [
            _res(
                returncode=1,
                stderr=(
                    "Error: deleting S3 Bucket (example-bucket): api error "
                    "BucketNotEmpty: The bucket you tried to delete is not empty."
                ),
            ),
            _res(returncode=0),
        ]
    )
    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: next(runs))

    purged: list[str] = []
    monkeypatch.setattr(orchestrator, "_purge_bucket_versions", lambda bucket: purged.append(bucket))

    orchestrator._terragrunt_destroy("x", "Module")
    assert purged == ["example-bucket"]


def test_destroy_bootstrap_accepts_backend_already_deleted(monkeypatch, tmp_path):
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: bootstrap_dir)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    def fake_run(command, **_kwargs):
        if command[:3] == ["terragrunt", "output", "-json"]:
            return _res(returncode=0, stdout='{"state_bucket":{"value":"x"}}')
        if command[:2] == ["terragrunt", "destroy"]:
            return _res(returncode=1, stderr="NoSuchBucket while saving state")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run", fake_run)
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: False)
    monkeypatch.setattr(orchestrator, "_table_exists", lambda _table, _region: False)

    orchestrator.destroy_bootstrap(_ctx(), interactive=False)


def test_destroy_bootstrap_uses_direct_cleanup_when_state_missing(monkeypatch, tmp_path):
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: bootstrap_dir)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: _res(returncode=1))
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda _bucket: True)
    monkeypatch.setattr(orchestrator, "_table_exists", lambda _table, _region: True)

    cleared: list[tuple[str, str, str, str]] = []
    deleted: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        orchestrator,
        "_clear_state_digest",
        lambda table, bucket, key, region: cleared.append((table, bucket, key, region)),
    )
    monkeypatch.setattr(
        orchestrator,
        "_delete_bootstrap_backend",
        lambda bucket, table, region: deleted.append((bucket, table, region)),
    )

    orchestrator.destroy_bootstrap(_ctx(), interactive=False)
    assert len(cleared) == 1
    assert len(deleted) == 1


def test_destroy_bootstrap_retries_digest_drift_then_succeeds(monkeypatch, tmp_path):
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: bootstrap_dir)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    calls = iter(
        [
            _res(returncode=0, stdout='{"state_bucket":{"value":"x"}}'),
            _res(returncode=1, stderr="state data in S3 does not have the expected content"),
            _res(returncode=0),
        ]
    )

    def fake_run(command, **_kwargs):
        if command[:3] == ["terragrunt", "output", "-json"]:
            return next(calls)
        if command[:2] == ["terragrunt", "destroy"]:
            return next(calls)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(orchestrator, "run", fake_run)
    monkeypatch.setattr(orchestrator, "_bucket_exists", lambda *_args: True)
    monkeypatch.setattr(orchestrator, "_table_exists", lambda *_args: True)
    monkeypatch.setattr(orchestrator.time, "sleep", lambda _seconds: None)

    cleared: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(
        orchestrator,
        "_clear_state_digest",
        lambda table, bucket, key, region: cleared.append((table, bucket, key, region)),
    )

    orchestrator.destroy_bootstrap(_ctx(), interactive=False)
    assert len(cleared) == 1


def test_terragrunt_destroy_raises_after_retry_failure(monkeypatch, tmp_path):
    module_dir = tmp_path / "module"
    module_dir.mkdir()
    monkeypatch.setattr(orchestrator, "_module_dir", lambda _module_path: module_dir)
    monkeypatch.setattr(orchestrator, "_terragrunt_output_exists", lambda _module_path: True)
    monkeypatch.setattr(orchestrator, "_print_result_output", lambda _result: None)

    runs = iter(
        [
            _res(returncode=1, stderr="Error: deleting S3 Bucket (example-bucket): BucketNotEmpty"),
            _res(returncode=1, stderr="still broken"),
        ]
    )
    monkeypatch.setattr(orchestrator, "run", lambda *_args, **_kwargs: next(runs))
    monkeypatch.setattr(orchestrator, "_purge_bucket_versions", lambda _bucket: None)

    with pytest.raises(orchestrator.CommandError, match="after bucket purge retry"):
        orchestrator._terragrunt_destroy("x", "Module")


def test_install_script_bucket_retry_path_on_addon_error(monkeypatch):
    ctx = _ctx()
    attempted: list[str] = []
    ensured: list[bool] = []

    def fake_apply(module_path: str, _module_name: str) -> None:
        attempted.append(module_path)
        if len(attempted) == 1:
            raise orchestrator.CommandError("NoSuchBucket install_collibra_dq.sh")

    monkeypatch.setattr(orchestrator, "_terragrunt_apply", fake_apply)
    monkeypatch.setattr(orchestrator, "_ensure_install_script_bucket", lambda _ctx: ensured.append(True))

    orchestrator._apply_addon_module("addons/collibra-dq-standalone", "Collibra DQ EC2 Instance", ctx)
    assert attempted == ["addons/collibra-dq-standalone", "addons/collibra-dq-standalone"]
    assert ensured == [True]


def test_runtime_profile_export_strategy_handles_shell_sensitive_secrets(tmp_path):
    profile_path = tmp_path / "collibra-dq.sh"
    secret_value = "9?E43v):Euq4n~hoNLb2ayfSC7Rl"
    password_value = "A9!5BU9fl9$@lPTN7ne76V@joiS"

    script = f"""
set -euo pipefail
shell_quote_single() {{
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}}

write_profile_export() {{
  local variable_name="$1"
  local variable_value="$2"
  printf 'export %s=' "$variable_name"
  shell_quote_single "$variable_value"
  printf '\\n'
}}

{{
  write_profile_export DQ_ADMIN_UI_USERNAME "admin"
  write_profile_export OWL_METASTORE_PASS "{secret_value}"
  write_profile_export DQ_ADMIN_USER_PASSWORD "{password_value}"
}} > "{profile_path}"

. "{profile_path}"
test "$DQ_ADMIN_UI_USERNAME" = "admin"
test "$OWL_METASTORE_PASS" = "{secret_value}"
test "$DQ_ADMIN_USER_PASSWORD" = "{password_value}"
"""

    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_installer_template_persists_admin_ui_username_and_avoids_bash_specific_q_exports():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert 'DQ_ADMIN_UI_USERNAME="admin"' in template
    assert "write_profile_export DQ_ADMIN_UI_USERNAME" in template
    assert "printf 'export OWL_METASTORE_PASS=%q\\n'" not in template


def test_installer_template_emits_admin_bootstrap_debug_artifacts():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert 'ADMIN_DEBUG_FILE="$ADMIN_DEBUG_DIR/admin-bootstrap-debug.env"' in template
    assert "write_admin_debug_file" in template
    assert "emit_admin_setup_debug_summary" in template
    assert "Password source:" in template
    assert "Password sha256:" in template
    assert "setup.sh admin/password hints (sanitized)" in template
    assert "[REDACTED_PASSWORD]" in template


def test_installer_template_uses_bootstrap_safe_admin_password_policy_and_generator():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert "grep -q '^[A-Za-z0-9_]*$' || return 1" in template
    assert "echo \"$password\" | grep -q '_' || return 1" in template
    assert "local alphabet='A-Za-z0-9_'" in template
    assert 'candidate="Aa9_$candidate"' in template
    assert "bootstrap-safe Collibra policy" in template


def test_installer_template_uses_shell_safe_refresh_exports_instead_of_percent_q():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert "update_export_var \"$PROFILE_SCRIPT\" \"OWL_METASTORE_PASS\" \"$PASSWORD\"" in template
    assert "printf 'OWL_METASTORE_PASS=%s\\n' \"$(shell_quote_single \"$PASSWORD\")\"" in template
    assert "PASSWORD_ESCAPED=$(printf '%q' \"$PASSWORD\")" not in template


def test_installer_template_overrides_vendor_encrypted_admin_password_in_owl_env():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert "Vendor setup.sh writes the encrypted admin password into owl-env.sh" in template
    assert '_owl_env_set DQ_ADMIN_USER_PASSWORD "$BOOTSTRAP_DQ_ADMIN_USER_PASSWORD"' in template
    assert '_owl_env_set DQ_ADMIN_USER_EMAIL "$BOOTSTRAP_DQ_ADMIN_USER_EMAIL"' in template


def test_installer_template_caches_bootstrap_admin_credentials_before_resourcing_owl_env():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert 'BOOTSTRAP_DQ_ADMIN_USER_PASSWORD="$DQ_ADMIN_USER_PASSWORD"' in template
    assert 'BOOTSTRAP_DQ_ADMIN_USER_EMAIL="$DQ_ADMIN_USER_EMAIL"' in template
    assert '_owl_env_set DQ_ADMIN_USER_PASSWORD "$BOOTSTRAP_DQ_ADMIN_USER_PASSWORD"' in template
    assert '_owl_env_set DQ_ADMIN_USER_EMAIL "$BOOTSTRAP_DQ_ADMIN_USER_EMAIL"' in template


def test_installer_template_restarts_owlweb_after_rewriting_admin_env():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert "Restart owl-web unconditionally" in template
    assert '"$OWL_MANAGE_SCRIPT" stop=owlweb || true' in template
    assert '"$OWL_MANAGE_SCRIPT" start=owlweb' in template
    assert 'if [ "$LICENSE_CONFIGURED" = true ]; then' not in template


def test_installer_template_reconciles_admin_password_in_metastore():
    template_path = (
        Path(__file__).resolve().parents[2]
        / "module/application/collibra-dq-standalone/user-data/install_collibra_dq.sh.tmpl"
    )
    template = template_path.read_text(encoding="utf-8")

    assert "Installing bundled PostgreSQL 12 client for SCRAM-compatible metastore access" in template
    assert "ensure_bundled_postgresql_client()" in template
    assert "generate_bcrypt_hash()" in template
    assert "reconcile_admin_password()" in template
    assert "update users set password =" in template
    assert "Admin password reconciled in metastore." in template
