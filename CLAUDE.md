# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS Collibra DQ Starter — IaC platform for deploying Collibra DQ (standalone) on AWS using Terraform + Terragrunt, orchestrated by a Python CLI (`dqctl`). The project path contains spaces — always use `--no-editable` with `uv run`.

## Build & Run Commands

```bash
# Install/sync dependencies
uv sync

# Run CLI (use --no-editable because project path contains spaces)
uv run --no-editable python -m collibra_dq_starter.cli --help
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full --parallel

# Run all tests (coverage gate: 75%)
python -m pytest

# Run a single test file
python -m pytest tests/unit/test_cli.py

# Run a single test
python -m pytest tests/unit/test_cli.py::test_function_name -v

# Run only integration tests
python -m pytest -m integration

# Pre-commit checks (terraform fmt, tflint, tfsec, checkov, shellcheck, detect-secrets, markdownlint)
pre-commit run --all-files
```

## Architecture

**Three-layer design:**

1. **Control Plane** — Python CLI (`src/collibra_dq_starter/cli.py` → `orchestrator.py` → `shell.py`) executes Terragrunt modules in deterministic dependency order.
2. **Data Plane** — ALB (HTTP :80) → EC2 Collibra DQ (:9000) → RDS PostgreSQL. EC2 uses IAM role + SSM + VPC endpoints for private S3/SSM connectivity.
3. **Backend** — Stack-scoped S3 tfstate bucket + DynamoDB lock table. Shared artifact bucket is env-independent.

**Deploy order (enforced by orchestrator):**
bootstrap → shared/artifact-bucket → vpc → vpc-endpoints → sg-rds → rds → install-script-bucket → package-upload → sg-collibra-dq → collibra-dq-standalone → rotation-restart → sg-alb → alb → target-group-attachment

**Key directories:**

- `src/collibra_dq_starter/` — Python CLI (cli.py ~95 lines, orchestrator.py ~1016 lines, shell.py ~49 lines)
- `module/` — Reusable Terraform modules (application, database, network, security, storage, operations)
- `env/stack/collibra-dq/` — Live Terragrunt stack with `root.hcl` driving environment-based defaults
- `tests/` — unit, integration, regression tests
- `docs/adr/` — 17 Architecture Decision Records (8 core + 3 stack + 4 component + 2 module)
- `packages/collibra-dq/` — Local installer artifact (2.7 GB .tar, gitignored)

## Environment Configuration

All config is environment-driven. Key variables:

- `TF_VAR_environment` — `dev` or `prod` (controls AZ count, NAT topology, instance sizes, HA settings)
- `TF_VAR_region` — any valid AWS region (e.g. `eu-west-1`, `us-east-1`, `ap-southeast-2`)
- `COLLIBRA_DQ_LICENSE_KEY` — required for addon/full deploy
- `COLLIBRA_DQ_AMI_ID` — auto-resolved to latest RHEL 7.9 if unset
- `TG_*` variables — override stack naming and resource defaults in `root.hcl`

## Test Structure

- **Unit** (`tests/unit/`) — CLI parsing, orchestrator helpers, shell wrapper. No AWS needed.
- **Integration** (`tests/integration/`) — Terragrunt HCL validation, terraform fmt checks. Marker: `integration`.
- **Regression** (`tests/regression/`) — S3 versioned cleanup, bootstrap lifecycle, install-script recovery, standalone hook behavior.
- **AWS smoke** (`tests/integration/aws/`) — Full deploy/destroy lifecycle. Marker: `aws`. Opt-in, requires real AWS credentials.

pytest config is in `pyproject.toml`. Coverage is enforced at 75% with `--cov=collibra_dq_starter`.

## Commit Convention

Conventional Commits: `<type>(optional-scope): <imperative description>`

Examples: `feat(orchestrator):`, `fix(alb):`, `docs(readme):`, `chore(ci):`

## Key Design Decisions

- **Service health > bootstrap status** — ALB target `healthy` is authoritative; cloud-init errors are non-blocking if app serves on :9000 (ADR-008).
- **HTTP-only default** — HTTPS requires explicit ACM + listener config (ADR-006).
- **Standalone hook opt-in** — `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true` for direct-apply target attachment reconciliation (ADR-007).
- **Shared artifact model** — Upload package once to shared bucket, all envs read from it (ADR-004).
- **Stack-scoped backend** — Separate S3 + DynamoDB per stack, not global (ADR-003).
- **Cost-optimized dev** — 2 AZ, single NAT, smaller instances. Prod: 3 AZ, multi-NAT, HA (ADR-005).
- **Stage-based parallel execution** — `--parallel` flag runs independent modules concurrently within each dependency stage. Sequential by default.
