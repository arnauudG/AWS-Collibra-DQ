# AWS Collibra DQ

Infrastructure as Code (IaC) package for deploying **Collibra DQ (Standalone)** on AWS with Terraform + Terragrunt, orchestrated by a `uv`-run Python CLI.

## Table of Contents

- [Overview](#overview)
- [Product Intent (PRD)](#product-intent-prd)
- [Platform Design (PSD)](#platform-design-psd)
- [Architecture](#architecture)
- [Package Contents](#package-contents)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Operational Runbook](#operational-runbook)
- [Components](#components)
- [Architecture Decision Records (ADR)](#architecture-decision-records-adr)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)
- [Contributing](#contributing)
- [Additional Documentation](#additional-documentation)

## Overview

This package deploys a complete Collibra DQ stack in AWS:

- **VPC** with public/private subnets
- **VPC Endpoints** for SSM and S3 private access
- **RDS PostgreSQL** for DQ metastore
- **EC2 standalone node** running Collibra DQ
- **ALB** exposing the application endpoint
- **Shared artifact bucket** (env-independent, upload once, deploy everywhere)
- **Rotation restart automation** (EventBridge -> SSM -> service restart)
- **Stack-scoped state backend** (S3 + DynamoDB)

Everything runs through:

```bash
uv run --no-editable python -m collibra_dq_starter.cli ...
```

`--no-editable` is recommended for reliability when project paths include spaces.

## Product Intent (PRD)

### Problem Statement

Teams need a repeatable way to deploy Collibra DQ in AWS for development and controlled production rollout, without manual AWS console steps and without hidden operational glue.

### Objectives

- Provide deterministic deploy/destroy flows through a single CLI.
- Keep dev cost optimized by default (single VPC, minimum valid subnet footprint, single-AZ RDS).
- Keep deployment idempotent across repeated runs.
- Keep runtime operational visibility (ALB health, SSM diagnostics, rotation restart observability).

### Non-Goals

- Not a multi-tenant platform.
- Not a Kubernetes/ECS deployment model.
- Not a managed CI/CD service.
- Not HTTPS-by-default (HTTP listener is default unless explicitly extended with ACM/certificate config).

### Success Criteria

- `deploy --target full` completes without manual remediation.
- ALB target becomes `healthy` and app is reachable via ALB DNS over HTTP.
- `destroy --target all` completes cleanly even with versioned S3 buckets.

## Platform Design (PSD)

### Control Plane

- `uv` runs Python orchestrator (`collibra_dq_starter.cli`).
- Orchestrator executes Terragrunt modules in explicit dependency order.
- State backend is bootstrapped in dedicated stack (`bootstrap`) with S3 + DynamoDB.

### Data Plane

- ALB (internet-facing) forwards to EC2 Collibra DQ (`:9000`).
- EC2 connects to RDS PostgreSQL (`dqMetastore`).
- Package artifacts are read from shared S3 artifact bucket.
- Rendered install script is stored in per-env S3 install-script bucket.

### Operational Contracts

- Full deploy path owns target registration through module ordering, including `alb/target-group-attachment`.
- Standalone direct apply hook for target re-attachment is opt-in only (`COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true`).
- ALB default listener is HTTP (`80`), so browser endpoint is `http://<alb-dns>/`.

## Architecture

```
                        Internet / Client Browser
                                  |
                                  v
                      +-------------------------+
                      | Application Load        |
                      | Balancer (HTTP default) |
                      +-----------+-------------+
                                  |
                                  v
         +------------------------------------------------------+
         | AWS Account                                          |
         |                                                      |
         |   +-------------------- VPC ----------------------+  |
         |   |                                               |  |
         |   |  Private Subnet(s)                            |  |
         |   |  +---------------------+                      |  |
         |   |  | EC2 Collibra DQ     |<-- S3 package ------+--+-- S3
         |   |  | (port 9000)         |                      |  |
         |   |  +----------+----------+                      |  |
         |   |             |                                 |  |
         |   |             v                                 |  |
         |   |      +-------------+                          |  |
         |   |      | RDS Postgres|                          |  |
         |   |      +-------------+                          |  |
         |   |                                               |  |
         |   |  VPC Endpoints (SSM, S3)                      |  |
         |   +-----------------------------------------------+  |
         |                                                      |
         +------------------------------------------------------+
```

## Package Contents

```
AWS Classic Collibra Data Quality/
├── pyproject.toml                    # uv package + entrypoint
├── uv.lock                           # lockfile
├── .pre-commit-config.yaml           # checks and formatting
├── README.md                         # this guide
├── CONTRIBUTING.md                   # contribution/release checklist
│
├── src/collibra_dq_starter/
│   ├── cli.py                        # argparse interface
│   ├── orchestrator.py               # deploy/destroy orchestration
│   └── shell.py                      # subprocess wrapper
│
├── env/stack/collibra-dq/            # live Terragrunt stack
│   ├── root.hcl                      # top-level stack config
│   ├── bootstrap/                    # backend resources
│   ├── shared/                       # shared artifact bucket (env-independent)
│   ├── network/                      # vpc + endpoints
│   ├── database/                     # rds + sg
│   └── addons/                       # package + ec2 + alb + rotation restart
│
├── module/                           # reusable Terraform modules
│   └── operations/secret-rotation-restart/  # event-driven restart + alarms
└── packages/collibra-dq/             # local Collibra installer artifact
```

## Prerequisites

### Required Tools

| Tool | Purpose | Minimum Version |
|------|---------|-----------------|
| `uv` | Python runtime + CLI execution | latest |
| `python` | runtime for CLI | >= 3.10 |
| `terraform` | infrastructure provisioning | >= 1.5.0 |
| `terragrunt` | orchestration and dependency handling | latest |
| `aws` cli | AWS API access and auth | v2.x |

### AWS Permissions

Credentials should allow creation/update of:

- VPC, subnets, route tables, NAT gateway
- EC2, security groups, IAM role/profile
- RDS PostgreSQL
- S3 buckets/objects
- DynamoDB table
- ALB, target group, listeners
- CloudWatch logs (depending on module settings)

## Environment Variables

All runtime configuration is environment-driven.

### Required (for deploy/destroy lifecycle)

| Variable | Description |
|----------|-------------|
| `TF_VAR_environment` | target environment (`dev` or `prod`) |
| `TF_VAR_region` | target region (`eu-west-1`, `us-east-1`, `eu-central-1`) |
| `AWS_PROFILE` or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | AWS authentication |

### Required for `deploy --target addon` / `deploy --target full`

| Variable | Description |
|----------|-------------|
| `COLLIBRA_DQ_LICENSE_KEY` | Collibra license key |

### Optional but recommended for `deploy --target addon` / `deploy --target full`

| Variable | Description |
|----------|-------------|
| `COLLIBRA_DQ_PACKAGE_URL` | Optional override package artifact URL (`s3://...` or `https://...`). If unset, orchestrator resolves shared artifact S3 URL automatically. |
| `COLLIBRA_DQ_ADMIN_PASSWORD` | Admin password (case-sensitive). Must be 8-72 chars with upper/lower/digit/special and must not contain `admin`; if unset/invalid, installer auto-generates a compliant password for non-interactive setup. |
| `COLLIBRA_DQ_AMI_ID` | Override EC2 AMI ID directly. If unset, CLI auto-resolves latest RHEL 7.9 AMI per region. |
| `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK` | Enables direct-standalone after-hook to auto-reconcile ALB target attachment (`false` by default; not needed for orchestrated full deploy). |
| `COLLIBRA_DQ_ENABLE_ROTATION_RESTART` | Enable EventBridge->SSM restart on RDS secret rotation (`true` by default) |
| `COLLIBRA_DQ_ENABLE_ROTATION_ALARMS` | Enable CloudWatch alarms for rotation restart failures (`true` by default) |
| `COLLIBRA_DQ_ROTATION_ALARM_ACTIONS` | Comma-separated alarm action ARNs (for example SNS topics) |
| `COLLIBRA_DQ_ROTATION_OK_ACTIONS` | Comma-separated OK action ARNs |

### Collibra / Owl terminology mapping

- `Owl DQ` and `Collibra DQ` are equivalent in this project.
- `OWL_BASE` and `OWL_HOME` refer to the same install directory.
- `METASTORE_USER`/`METASTORE_PASS` correspond to `OWL_METASTORE_USER`/`OWL_METASTORE_PASS`.
- Username and password values are case-sensitive.
- License activation only requires `COLLIBRA_DQ_LICENSE_KEY`; expiration date is not used in this workflow.
- RDS master password is managed by AWS Secrets Manager and refreshed on app restart/start; rotation can also trigger restart automatically.
- Rotation guardrails create CloudWatch alarms for EventBridge target failures and failed SSM restart commands.

### Dynamic top-level config (`TG_*`)

These drive reusable naming and defaults in `env/stack/collibra-dq/root.hcl`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `TG_ORG` | `dq` | organization/name prefix |
| `TG_PROJECT` | `Collibra-DQ-Starter` | tag value |
| `TG_COST_CENTER` | `Engineering` | tag value |
| `TG_EXPECTED_ACCOUNT_ID` | unset | safety check against wrong account |
| `TG_ACCOUNT_ID` | `unknown-account` fallback | static validation fallback |
| `TG_COLLIBRA_DQ_VPC_CIDR` | env-based default | VPC CIDR |
| `TG_VPC_AZ_COUNT` | `2` in dev, `3` in prod | AZ/subnet footprint (clamped to 2-3) |
| `TG_SINGLE_NAT_GATEWAY` | env-based default | NAT topology |
| `TG_ENABLE_FLOW_LOG` | env-based default | VPC flow log |
| `TG_RDS_INSTANCE_CLASS` | env-based default | DB class |
| `TG_RDS_ALLOCATED_STORAGE` | `100` | initial DB storage |
| `TG_RDS_MAX_ALLOCATED_STORAGE` | env-based default | autoscaling storage max |
| `TG_RDS_DELETION_PROTECTION` | env-based default | DB deletion guard |
| `TG_RDS_MULTI_AZ` | `false` in dev, `true` in prod | high availability |
| `TG_RDS_BACKUP_RETENTION` | env-based default | backup days |
| `TG_COLLIBRA_DQ_INSTANCE_TYPE` | env-based default | EC2 instance type |
| `TG_COLLIBRA_DQ_VOLUME_SIZE` | env-based default | EC2 root volume size |
| `TG_ALB_DELETION_PROTECTION` | env-based default | ALB deletion guard |

## Quick Start

```bash
# 1) Clone
git clone <repository-url>
cd "AWS Classic Collibra Data Quality"

# 2) Install/sync python package
uv sync

# 3) Export required values
export TF_VAR_environment=dev
export TF_VAR_region=eu-west-1
export AWS_PROFILE=my-profile
# Optional: if omitted, installer auto-generates a policy-compliant password.
export COLLIBRA_DQ_ADMIN_PASSWORD='<password>'
export COLLIBRA_DQ_LICENSE_KEY='<license-key>'
# 4) Deploy full stack (package auto-uploads from packages/collibra-dq/ if not in S3)
uv run --no-editable python -m collibra_dq_starter.cli deploy --target full
```

## Usage

### Command Reference

```bash
# Help
uv run --no-editable python -m collibra_dq_starter.cli --help

# Deploy full stack: bootstrap + infra + addons
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full

# Deploy bootstrap + infrastructure only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target stack

# Deploy addons only (requires stack dependencies already in place)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target addon

# Deploy package artifact bucket/content only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target package

# Deploy backend only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target bootstrap

# Destroy addons only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target addon

# Destroy package artifact bucket/content only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target package

# Destroy addons + infra, keep backend
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target stack

# Destroy everything, including backend
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target all

# Non-interactive destroy (CI/automation)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target all --yes
```

### Target Matrix

| Command | Target | What it does |
|---------|--------|--------------|
| `deploy` | `bootstrap` | deploy/import state backend only |
| `deploy` | `stack` | backend + core infra (network) |
| `deploy` | `addon` | backend + addon/app layers only |
| `deploy` | `package` | backend + package artifact module only |
| `deploy` | `full` | stack + DB + app + ALB + rotation ops (auto-uploads package if missing) |
| `destroy` | `addon` | app + DB + ALB layers only |
| `destroy` | `package` | package upload module only |
| `destroy` | `stack` | addon + core infra, preserve backend + shared bucket |
| `destroy` | `all` | addon + infra + package + shared bucket + backend teardown |

### Artifact Flow

Package artifacts use a **shared artifact bucket** (`<account>-<org>-collibra-dq-artifacts-<region>`) that is env-independent. Upload the package once and all environments read from it.

```bash
# Option A: Explicit upload (independent lifecycle)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target package

# Option B: Auto-upload during full deploy
# Place the .tar in packages/collibra-dq/ and run full deploy — the CLI auto-uploads if missing from S3.
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full
```

**Upgrade workflow:** drop a new `.tar` in `packages/collibra-dq/`, run `deploy --target package`. All environments pick up the new package on next EC2 redeploy.

The per-env install-script bucket (which holds the rendered install script with env-specific secrets) is created automatically and managed separately.

## Operational Runbook

This runbook is the recommended self-service flow for operators.

Cost-optimized dev defaults:

- single VPC
- 2 AZ network footprint (2 public + 2 private subnets)
- single NAT gateway
- RDS single-AZ (`multi_az=false`)

### 1) Preflight

```bash
aws sts get-caller-identity
uv run --no-editable python -m collibra_dq_starter.cli --help
```

Required context:

- `TF_VAR_environment`
- `TF_VAR_region`
- `AWS_PROFILE` (or access key env vars)
- `COLLIBRA_DQ_LICENSE_KEY`

For direct `terragrunt`/`terraform` applies on the standalone module, set:

```bash
export COLLIBRA_DQ_AMI_ID=<rhel-7.9-ami-id>
```

### 2) Deploy

```bash
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full
```

### 3) Verify target registration and health

```bash
export REGION="eu-west-1"
export TG_ARN="<target-group-arn>"

aws elbv2 describe-target-health \
  --target-group-arn "$TG_ARN" \
  --region "$REGION" \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason,TargetHealth.Description]' \
  --output table
```

Expected lifecycle:

- `initial` + `Elb.RegistrationInProgress` during startup.
- `healthy` when DQ Web is listening on `:9000`.

If output is empty, no target is registered.

### 4) If instance was replaced, confirm target attachment sync

When `addons/collibra-dq-standalone` is re-applied with instance replacement:

- in orchestrated deploys, target-group attachment is handled by ordered module execution
- in direct standalone applies, after-hook auto-reconcile is available only when `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true`

If the hook is skipped or fails in your execution context, run this fallback command:

```bash
cd "env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment"
terragrunt apply --auto-approve
```

### 5) Pull runtime diagnostics through SSM

```bash
export INSTANCE_ID="$(cd "env/stack/collibra-dq/addons/collibra-dq-standalone" && terragrunt output -raw instance_id)"
export REGION="eu-west-1"

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "cloud-init status --long || true",
    "cat /var/lib/collibra-dq-install/status.env || true",
    "systemctl status cloud-final --no-pager -l || true",
    "systemctl status collibra-dq --no-pager -l || true",
    "ss -tlnp | egrep \"9000|9101\" || true",
    "tail -n 200 /var/log/collibra-dq-install.log || true",
    "tail -n 120 /var/log/collibra-dq-setup.log || true"
  ]' \
  --query 'Command.CommandId' --output text)

sleep 5
aws ssm get-command-invocation \
  --region "$REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '[Status,StatusDetails,StandardOutputContent,StandardErrorContent]' \
  --output json
```

### 6) Verify ALB endpoint from operator machine

Disable AWS CLI pager first to prevent commands from dropping into `(END)` output views:

```bash
export AWS_PAGER=""
```

Resolve ALB DNS from target group and verify external response:

```bash
export TG_ARN="<target-group-arn>"
export REGION="eu-west-1"

LB_ARN=$(aws elbv2 describe-target-groups \
  --region "$REGION" \
  --target-group-arns "$TG_ARN" \
  --query 'TargetGroups[0].LoadBalancerArns[0]' \
  --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --region "$REGION" \
  --load-balancer-arns "$LB_ARN" \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

echo "$ALB_DNS"
curl -I "http://$ALB_DNS/"
```

Expected: HTTP `302` redirect to `/login` or HTTP `200`.

### 7) Interpret bootstrap status correctly

Use this precedence when values disagree:

1. ALB target health (`healthy` is authoritative for traffic readiness).
2. Instance listener (`ss -tlnp` shows `*:9000`).
3. Local HTTP probe (`curl http://127.0.0.1:9000/` returns `200` or `302`).
4. `cloud-init` and `/var/lib/collibra-dq-install/status.env`.

If `status.env` shows `PHASE=HANDOFF` with `LAST_EXIT_CODE=1/2` but checks 1-3 are green, treat deployment as operational and classify it as a non-blocking bootstrap warning.

## Components

### Bootstrap

Creates and manages stack backend resources:

- S3 bucket for tfstate
- DynamoDB table for state lock
- import-aware behavior if resources exist but state is missing

### Network

- VPC and subnets
- VPC endpoints for SSM and S3 access from private subnet workloads

### Data Layer

- RDS PostgreSQL instance
- dedicated RDS security group with controlled ingress

### Application Layer

- EC2 standalone Collibra DQ install/bootstrap
- ALB + target group attachment

### Operations Layer

- runtime secret refresh + DB auth verification on service start
- event-driven restart on RDS secret rotation (`addons/collibra-dq-standalone/rotation-restart`)
- CloudWatch alarms for restart orchestration failures

### Artifact Layer

- **Shared artifact bucket** (`shared/artifact-bucket`) — env-independent, holds DQ package
- **Per-env install-script bucket** (`addons/collibra-dq-standalone/install-script-bucket`) — holds rendered install script with secrets
- Package upload module (`addons/collibra-dq-standalone/package-upload`) — uploads to shared bucket
- Can be deployed separately with `deploy --target package`

## Architecture Decision Records (ADR)

### ADR-001: CLI-first orchestration

Context:
Deploy/destroy spans backend bootstrap, shared storage, network, database, compute, ALB, and post-deploy recovery logic. Plain Terragrunt stacks alone do not express all runtime safety checks and retries cleanly.

Decision:
Use a Python CLI (`collibra_dq_starter.cli`) as the primary control plane and let it call Terragrunt in explicit order.

Rationale:
This centralizes retry behavior, bucket purge fallback, bootstrap recovery, package upload checks, and environment validation in one place.

Consequences:
- Operators should prefer `uv run --no-editable python -m collibra_dq_starter.cli ...`
- Direct Terragrunt use remains possible for debugging, but is not the primary operating model

### ADR-002: Environment-driven configuration over per-client files

Context:
This package is meant to be reused across accounts, environments, and customers without maintaining divergent code branches.

Decision:
Use environment variables (`TF_VAR_*`, `TG_*`, `COLLIBRA_*`) as the main configuration interface.

Rationale:
This reduces repo sprawl, keeps CI/CD integration simple, and supports secure secret injection from external stores.

Consequences:
- Documentation must clearly separate required, optional, and override variables
- Runtime behavior depends on operator discipline and environment hygiene

### ADR-003: Stack-scoped backend

Context:
Terraform state is highly sensitive and operationally critical. Sharing state backends across unrelated stacks increases blast radius and teardown complexity.

Decision:
Create dedicated backend resources per stack/environment (`bootstrap` S3 + DynamoDB).

Rationale:
This isolates failure domains and makes full teardown possible without affecting other projects.

Consequences:
- Bootstrap must be created before the rest of the stack
- Full destroy must handle backend deletion as a special case

### ADR-004: Shared artifact bucket plus per-environment install-script bucket

Context:
The large Collibra package artifact is environment-agnostic, while the rendered install script contains environment-specific values and secrets.

Decision:
Use two S3 bucket roles:
- shared artifact bucket for reusable package payloads
- per-environment install-script bucket for rendered bootstrap/install script

Rationale:
This avoids re-uploading the large package for every environment while keeping environment-specific script content isolated.

Consequences:
- `COLLIBRA_DQ_PACKAGE_URL` is optional in normal flow
- package lifecycle and install-script lifecycle are intentionally separate

### ADR-005: Cost-optimized dev defaults

Context:
The primary near-term usage is development and validation, not production-scale resilience.

Decision:
Default dev to a reduced-cost topology:
- one VPC
- minimum valid subnet footprint
- single NAT gateway
- single-AZ RDS

Rationale:
This keeps iteration cost acceptable while preserving the minimum AWS topology required by ALB and RDS.

Consequences:
- Dev is not equivalent to prod HA posture
- Documentation must call out where prod should diverge

### ADR-006: HTTP-only ALB by default

Context:
HTTPS requires certificate lifecycle, ACM ownership, and domain decisions that are not always available during initial environment bring-up.

Decision:
Default the ALB to HTTP listener only.

Rationale:
This removes certificate dependencies from baseline deployment and shortens time-to-first-working-environment.

Consequences:
- Operators must use `http://<alb-dns>/` unless they explicitly add HTTPS
- Browser “refused to connect” on `https://` is expected in default configuration

### ADR-007: Direct standalone hook is opt-in

Context:
Automatic target re-attachment is helpful during direct standalone applies, but can interfere with orchestrated full-stack deploy if ALB outputs are not ready yet.

Decision:
Keep the direct standalone `after_hook` disabled by default and require `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true` to enable it.

Rationale:
Full deploy already owns target-group attachment in module order. The hook is only needed for targeted standalone-only workflows.

Consequences:
- Full deploy remains stable
- Direct module operators still have an automation path when they explicitly choose it

### ADR-008: Service health over bootstrap status

Context:
Cloud-init/bootstrap can report `PHASE=HANDOFF` and non-zero exit codes even when the application is already serving traffic and ALB health is good.

Decision:
Treat runtime service signals as the source of truth:
- ALB target healthy
- process listening on `:9000`
- local HTTP probe returns `200` or `302`

Rationale:
This matches actual platform usability better than cloud-init exit state alone.

Consequences:
- Runbooks explicitly distinguish blocking vs non-blocking bootstrap warnings
- Operators should not destroy/rebuild solely because `status.env` is non-zero if service health is confirmed

## Troubleshooting

### AWS auth errors

Run:

```bash
aws sts get-caller-identity
```

Confirm either `AWS_PROFILE` is valid, or access key env vars are set correctly.

### Package upload/install issues

- confirm installer exists under `packages/collibra-dq/`
- run `deploy --target full` with required Collibra secrets
- inspect EC2 install logs with SSM if ALB target remains unhealthy

### Target unhealthy behind ALB

- wait for installation completion (can take several minutes)
- verify SG rules between ALB and EC2
- confirm application is listening on port `9000`
- if `describe-target-health` returns no rows, confirm standalone apply hook ran; otherwise run fallback re-apply of `alb/target-group-attachment`

### cloud-init shows `status: error` but target is healthy

Use service health as the runtime source of truth:

- ALB target = `healthy`
- `ss -tlnp` shows listener on `*:9000`
- local HTTP probe returns `200` or `302`

In this case, treat cloud-init failure as non-blocking and continue. Inspect `/var/lib/collibra-dq-install/status.env` and `/var/log/collibra-dq-install.log` for the exact phase/exit code.

### ALB returns 503

Run these checks in order:

1. Verify target registration (`describe-target-health` is not empty).
2. Verify target state is `healthy`.
3. Verify app listener exists on instance (`*:9000`).
4. Verify local probe on instance returns `200` or `302`.
5. Verify ALB DNS response from operator machine.

If `describe-target-health` is empty after instance replacement, run the fallback re-apply:

```bash
cd "env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment"
terragrunt apply --auto-approve
```

Then poll until `healthy`:

```bash
for i in {1..20}; do
  aws elbv2 describe-target-health \
    --region "$REGION" \
    --target-group-arn "$TG_ARN" \
    --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason,TargetHealth.Description]' \
    --output table
  sleep 15
done
```

### Browser shows "refused to connect" on ALB DNS

Most common cause in this stack: opening HTTPS on an HTTP-only listener.

- Default ALB listener is `HTTP :80`
- Use `http://<alb-dns>/` (not `https://<alb-dns>/`) unless you explicitly configured HTTPS listener + ACM cert

### State lock or backend mismatch

- confirm no concurrent apply/destroy is running
- for wrong account/region issues, use `TG_EXPECTED_ACCOUNT_ID` and explicit `--env/--region`

### Rotation event happened but app did not restart

- check EventBridge rule status in `addons/collibra-dq-standalone/rotation-restart`
- inspect CloudWatch alarms for rotation-restart failures
- verify instance is managed by SSM and online (`aws ssm describe-instance-information`)
- verify restart hook logs on instance (`journalctl -u collibra-dq`)

## Security Notes

1. Terraform state can contain sensitive data; protect backend access.
2. Never commit secrets into repo files.
3. Keep Collibra secrets in CI/CD secret stores or secure shell/session vars.
4. Prefer private subnet + SSM access model for app hosts.
5. Enable stricter prod settings (`TG_RDS_DELETION_PROTECTION`, `TG_RDS_MULTI_AZ`, TLS/certs where applicable).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching strategy, commit style, and release checklist.

## Additional Documentation

| Document | Description |
|----------|-------------|
| [env/README.md](env/README.md) | Terragrunt directory overview |
| [env/stack/README.md](env/stack/README.md) | live stack map |
| [env/stack/collibra-dq/README.md](env/stack/collibra-dq/README.md) | stack-specific details |
| [module/application/collibra-dq-standalone/README.md](module/application/collibra-dq-standalone/README.md) | standalone module behavior and startup semantics |
| [packages/README.md](packages/README.md) | installer package location |
| [CONTRIBUTING.md](CONTRIBUTING.md) | process and release guidance |
