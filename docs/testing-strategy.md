# Testing Strategy

This document proposes and tracks a risk-based test strategy for the Collibra DQ AWS starter.

The repo now has an initial automated suite for Python unit/regression coverage plus local IaC integration checks. The next layer is AWS-backed smoke coverage that stays opt-in because it deploys and destroys real infrastructure.

## Current State

Implemented today:

- unit tests for CLI, shell wrapper, and orchestrator helpers
- regression tests for:
  - `BucketNotEmpty` destroy retry
  - bootstrap backend false-negative destroy
  - install-script bucket recovery
- local integration tests for:
  - `terragrunt hcl validate`
  - `terraform fmt -check -recursive`
  - pytest coverage plugin availability
- AWS smoke test harness gated behind explicit env flags and acknowledgement

Current local command:

```bash
python -m pytest
```

Current gating:

- coverage threshold: `75%`
- AWS smoke tests disabled by default

## Testing Goals

- Prevent regressions in deploy and destroy orchestration.
- Catch validation mistakes before Terragrunt reaches AWS.
- Detect changes that break target attachment ordering, S3 cleanup, or backend lifecycle.
- Separate fast local unit coverage from slower integration coverage.

## Risk Inventory

The current highest-risk areas are:

- CLI argument parsing and environment propagation.
- Project-root discovery when run outside repo root.
- AWS account and region validation.
- AMI resolution for Collibra DQ EC2.
- S3 object and bucket lifecycle behavior, especially versioned bucket destroy.
- Bootstrap backend import, drift recovery, and destroy behavior.
- Terragrunt apply/destroy retry behavior when `init` is required.
- Attachment ordering between standalone EC2, ALB, and target-group attachment.
- Shell-based hooks embedded in Terragrunt HCL.
- Operational acceptance logic where service health can be good despite bootstrap warnings.

## Proposed Test Pyramid

### Unit tests

Fast, local, no AWS, heavy use of monkeypatching and command stubs.

Target package:
- `src/collibra_dq_starter/cli.py`
- `src/collibra_dq_starter/orchestrator.py`
- `src/collibra_dq_starter/shell.py`

Recommended framework:
- `pytest`
- `pytest-mock` or builtin `monkeypatch`

Recommended scope:

1. CLI parsing and exit codes
   - `deploy` routes to orchestrator with correct target.
   - `destroy --yes` routes with `auto_approve=True`.
   - `--env` and `--region` set `TF_VAR_environment` and `TF_VAR_region`.
   - unknown command and `KeyboardInterrupt` return expected exit codes.

2. Shell wrapper behavior
   - `run()` returns stdout/stderr/returncode unchanged.
   - `run(check=True)` raises `CommandError` with command and combined output.
   - environment merging preserves caller overrides.

3. Project root discovery
   - respects `COLLIBRA_DQ_STARTER_ROOT` when valid.
   - rejects invalid override root.
   - discovers root from repo cwd.
   - discovers root from nested cwd.

4. Core env validation
   - missing `TF_VAR_environment` or `TF_VAR_region` fails.
   - unsupported env or region fails.
   - org default fallback works.

5. Deploy-target validation
   - `deploy addon/full` requires `COLLIBRA_DQ_LICENSE_KEY`.
   - `deploy package` requires local package file when no S3 package is available.
   - invalid `COLLIBRA_DQ_INSTALLATION_ID` fails fast.

6. AWS helper logic
   - `_parse_s3_url()` accepts valid paths and rejects malformed URLs.
   - `_artifact_bucket_name()`, `_install_script_bucket_name()`, `_bootstrap_bucket_name()`, `_bootstrap_table_name()` produce correct names.
   - `_resolve_latest_rhel7_ami()` rejects `None` and malformed output.

7. Terragrunt output/state detection
   - `_terragrunt_output_exists()` returns true for valid outputs.
   - falls back to `terragrunt state list` when outputs are `{}`.
   - returns false on invalid JSON or command failure.

8. Apply retry behavior
   - `_terragrunt_apply()` retries once after provider-init style failure.
   - `_terragrunt_apply()` surfaces non-retryable failures immediately.
   - `_terragrunt_apply_with_env()` merges extra env correctly.

9. Destroy retry behavior
   - `_terragrunt_destroy()` retries after `BucketNotEmpty`.
   - bucket name extraction from Terraform stderr is robust.
   - second destroy failure raises `CommandError`.

10. Bootstrap backend edge cases
   - `deploy_bootstrap()` handles state-present no-op apply.
   - `deploy_bootstrap()` imports when resources exist but state is missing.
   - `destroy_bootstrap()` uses direct cleanup path when state is unreadable.
   - `destroy_bootstrap()` treats “backend deleted but final state save failed” as success.
   - digest mismatch retry clears DynamoDB digest row and retries once.

11. Package/install bucket orchestration
   - `_ensure_shared_artifact_bucket()` skips apply when bucket already exists.
   - `_ensure_install_script_bucket()` retries once when bucket still missing after apply.
   - `_ensure_package_artifact_available()` skips when URL is HTTP.
   - `_ensure_package_artifact_available()` uploads when S3 object missing but local package exists.
   - `_ensure_package_artifact_available()` fails clearly when neither S3 nor local package is present.

12. Deploy/destroy order
   - `deploy("full")` calls bootstrap, shared, infra, then addon sequence in order.
   - `destroy("all")` destroys addon, infra, package, shared, then bootstrap in reverse order.
   - `destroy("stack")` preserves bootstrap and shared bucket.

### Regression tests

These lock in fixes for failures already observed in real runs.

1. Versioned bucket destroy regression
   - simulate `BucketNotEmpty` on package bucket and shared artifact bucket.
   - assert purge-and-retry path is invoked and destroy succeeds.

2. Bootstrap false-negative destroy regression
   - simulate successful backend deletion followed by S3 backend `NoSuchBucket` on final state save.
   - assert destroy is treated as success.

3. Install-script bucket recovery regression
   - simulate `NoSuchBucket` against `install_collibra_dq.sh` during EC2 deploy.
   - assert install-script bucket is re-applied and standalone deploy retried once.

4. Standalone hook regression
   - Terragrunt hook script should remain parse-safe in HCL.
   - default behavior should skip cleanly when `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK` is not `true`.
   - hook should avoid login-shell assumptions such as `PROMPT_COMMAND`.

5. Target attachment ordering regression
   - full deploy should not require ALB outputs during standalone apply.
   - target-group attachment should still run later in ordered deployment.

6. Health-vs-bootstrap regression
   - document and test acceptance rule where `PHASE=HANDOFF` with non-zero exit code is non-blocking if port `9000` and probe are healthy.

### Integration tests

These validate real Terragrunt/Terraform behavior with local commands and mocked or real cloud resources.

#### Local integration tests

No AWS required beyond local CLI/tool installation.

Implemented:

1. HCL validation matrix
   - runs `terragrunt hcl validate --working-dir env`
   - catches parsing issues in hooks and dependency wiring

2. Terraform formatting validation
   - runs `terraform fmt -check -recursive env module`

Pending:

3. Terraform module validation
   - run `terraform validate` for each reusable module once init/provider strategy is standardized for offline and CI use

4. CLI smoke tests with command stubs
   - run CLI against a stubbed `aws`, `terragrunt`, and `terraform` shim directory
   - assert emitted command sequence for each target

#### AWS-backed integration tests

These are slower and destructive, so they should stay manually invoked or scheduled.

Implemented:

1. Full stack smoke harness
   - deploy `full`
   - assert target group contains the current `instance_id`
   - assert target group reaches `healthy`
   - assert ALB HTTP endpoint returns `200` or `302`
   - destroy `all` in `finally`
   - disabled unless explicit env flags are set

Run command:

```bash
export RUN_AWS_INTEGRATION=1
export DQ_AWS_SMOKE_ACK=I_UNDERSTAND_THIS_WILL_DEPLOY_AND_DESTROY
export DQ_AWS_ENV=dev
export DQ_AWS_REGION=eu-west-1
python -m pytest -m aws
```

Planned extensions:

1. Bootstrap lifecycle
   - create backend.
   - destroy backend.
   - recreate backend.

2. Package lifecycle
   - deploy shared artifact bucket.
   - upload package from local file.
   - verify object exists at expected S3 URL.

3. Full deploy smoke
   - deploy `full` into dev.
   - verify instance, ALB, target-group attachment, and RDS exist.
   - verify ALB HTTP endpoint returns `200` or `302`.

4. Standalone replacement flow
   - replace EC2 instance.
   - verify new `instance_id` is attached to target group.
   - verify old instance is not left behind in target group.

5. Destroy all
   - destroy `all`.
   - verify versioned artifact buckets are purged and removed.
   - verify backend false-negative path does not fail final outcome.

6. Rotation restart path
   - rotate RDS secret or simulate rotation event.
   - verify EventBridge target and SSM command path execute.
   - verify `collibra-dq` service restart and alarm behavior.

## Suggested Test Layout

```text
tests/
├── unit/
│   ├── test_cli.py
│   ├── test_shell.py
│   ├── test_orchestrator_validation.py
│   ├── test_orchestrator_bootstrap.py
│   ├── test_orchestrator_s3.py
│   └── test_orchestrator_ordering.py
├── regression/
│   ├── test_bucket_not_empty_retry.py
│   ├── test_bootstrap_backend_deleted_success.py
│   ├── test_install_script_bucket_retry.py
│   └── test_standalone_hook_behavior.py
└── integration/
    ├── test_cli_command_sequence.py
    ├── test_terragrunt_hcl_validation.py
    └── aws/
        ├── test_bootstrap_lifecycle.py
        ├── test_full_deploy_smoke.py
        ├── test_standalone_replacement.py
        └── test_destroy_all.py
```

## Recommended First Implementation Slice

Completed first slice:

1. unit tests for `cli.py` and `shell.py`
2. orchestrator unit tests for bucket naming, env validation, and deploy ordering
3. regression tests for:
   - `BucketNotEmpty`
   - bootstrap backend deleted but final state save fails
   - install-script bucket retry
4. local integration tests for Terragrunt/Terraform parse and validate
5. one AWS-backed smoke harness for `deploy --target full`

Next slice:

1. split orchestrator tests by concern (`bootstrap`, `s3`, `ordering`)
2. add standalone hook-specific regression coverage
3. add AWS smoke assertions for ALB reachability and target health before destroy

## Tooling Recommendations

- `pytest` and `pytest-cov` are now configured as dev dependencies.
- Use `monkeypatch` heavily instead of real subprocess calls for unit tests.
- Consider a small command-fixture helper that returns scripted `CommandResult` objects by command tuple.
- For AWS-backed suites, gate execution behind an explicit marker or env var such as `RUN_AWS_INTEGRATION=1`.

## Coverage Targets

Current enforced target:

- unit + regression + local integration: `75%` coverage of `src/collibra_dq_starter/`

Current practical target:

- one passing local IaC validation suite
- one passing smoke flow for `deploy full` and `destroy all` when AWS integration is explicitly enabled

Next ratchet target:

- keep `75%` minimum and add deeper AWS smoke coverage for replacement flows and rotation-restart behavior before considering a move toward `85%`

Higher-value assertion target:

- every previously observed production failure mode has a dedicated regression test

## Open Gaps

- No current test harness exists for Terragrunt hook execution in rendered cache directories.
- No CI pipeline is defined in-repo yet for layered test execution.
- No synthetic health-check harness exists for validating `PHASE=HANDOFF` against actual service readiness.
