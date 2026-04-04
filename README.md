# AWS Collibra DQ

Infrastructure as Code package for deploying **Collibra DQ (Standalone)** on AWS with Terraform + Terragrunt, orchestrated by a Python CLI.

## Purpose

Deploy a complete Collibra DQ environment in AWS through a single CLI command. One command to deploy, one command to destroy, no manual console steps.

## Business context

Platform engineers and DevOps teams need a repeatable way to provision Collibra DQ for development and controlled production rollout. This package provides deterministic deploy/destroy flows, cost-optimized dev defaults, and runtime operational visibility.

## Scope

**In scope:** VPC networking with multi-AZ subnet layout, RDS PostgreSQL metastore, EC2 standalone Collibra DQ, ALB ingress, package artifact management, secret rotation restart automation, stack-scoped state backend.

**Out of scope:** multi-tenant deployment, Kubernetes/ECS, managed CI/CD, HTTPS by default (HTTP listener is the baseline; TLS/ACM is an explicit extension).

## Architecture

The stack deploys Collibra DQ as a standalone EC2 workload in a public subnet behind an internet-facing ALB, backed by RDS PostgreSQL in a private subnet.

See `collibra-dq-architecture.drawio` for the full diagram (two tabs: infrastructure topology with subnet layout, and operations flow).

### Network layout

The VPC is carved into `/22` subnets (1024 IPs each) using `cidrsubnet(cidr, 6, index)`, distributed across availability zones. Dev uses 2 AZs; prod uses 3.

```
VPC 10.11.0.0/16 (dev) · 10.21.0.0/16 (prod)
├── Public subnets (/22 per AZ)
│   ├── AZ-a: 10.11.0.0/22   ← ALB, EC2 Collibra DQ, NAT gateway
│   ├── AZ-b: 10.11.4.0/22   ← ALB target (spans both AZs)
│   └── AZ-c: 10.21.8.0/22   ← prod only, ALB + NAT per-AZ
│
└── Private subnets (/22 per AZ)
    ├── AZ-a: 10.11.8.0/22   ← VPC endpoints (SSM trio + S3 gateway)
    ├── AZ-b: 10.11.12.0/22  ← RDS PostgreSQL (primary)
    └── AZ-c: 10.21.20.0/22  ← prod only, RDS multi-AZ standby
```

Both ALB and RDS subnet groups require subnets in at least two availability zones — this is why the minimum footprint is 2 public + 2 private subnets. Override AZ count with `TG_VPC_AZ_COUNT` (clamped 2–3).

### Traffic flow

Browser requests arrive at the ALB in the public subnets on HTTP port 80. The ALB forwards to the EC2 Collibra DQ instance in the AZ-a public subnet on port 9000. The EC2 instance connects to RDS PostgreSQL in the AZ-b private subnet on port 5432 for the `dqMetastore` database. Administrative access to the EC2 instance is through SSM Session Manager via VPC endpoints in the private subnets.

### Security group chain

Traffic flows through three security groups in sequence:

```
Internet → sg-alb (:80) → sg-collibra-dq (:9000) → sg-rds (:5432)
```

- `sg-alb` allows HTTP/HTTPS from the internet, egress only to port 9000 within the VPC
- `sg-collibra-dq` allows ingress on 9000 from `sg-alb` only (plus health check and Spark UI ports from VPC CIDR), egress to RDS on 5432
- `sg-rds` allows ingress on 5432 from `sg-collibra-dq` only

### Storage model

Two S3 buckets serve different purposes. The **shared artifact bucket** (`<account>-<org>-collibra-dq-artifacts-<region>`) is environment-independent and holds the large DQ package — upload once, all environments read from it via the S3 gateway VPC endpoint. The **per-env install script bucket** (`<account>-<org>-<env>-collibra-dq-packages-<region>`) holds the rendered install script containing environment-specific secrets.

### VPC endpoints

Four VPC endpoints keep control-plane and storage traffic off the public internet:

- `ssm`, `ssmmessages`, `ec2messages` — Interface endpoints in private subnets for SSM Session Manager
- `s3` — Gateway endpoint attached to route tables for package downloads from S3

### NAT gateway topology

Dev uses a single NAT gateway in AZ-a (cost optimization). Prod uses one NAT gateway per AZ (resilience). Override with `TG_SINGLE_NAT_GATEWAY`.

### Secret rotation and restart

RDS uses AWS-managed master secrets. When Secrets Manager rotates the password, an EventBridge rule detects the rotation event and invokes SSM RunCommand to restart the `collibra-dq` systemd service on the EC2 instance. Pre-start hooks refresh the latest secret and verify DB auth before the service starts. CloudWatch alarms monitor both EventBridge target invocation failures and failed SSM restart commands.

### State backend

A dedicated S3 bucket (versioned, encrypted) + DynamoDB lock table is bootstrapped per stack/environment as the first deployment step. This isolates state across environments and prevents cross-environment interference.

## Module execution order

The CLI orchestrator (`collibra_dq_starter.cli`) executes Terragrunt modules in deterministic order. Direct Terragrunt usage is advanced-only.

### Deploy order

| Step | Module path | Domain | bootstrap | stack | addon | package | full |
|------|-------------|--------|:---------:|:-----:|:-----:|:-------:|:----:|
| 1 | `bootstrap` | State | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | `shared/artifact-bucket` | Storage | | ✓ | ✓ | ✓ | ✓ |
| 3 | `network/vpc` | Network | | ✓ | | | ✓ |
| 4 | `network/vpc-endpoints` | Network | | ✓ | | | ✓ |
| 5 | `addons/.../install-script-bucket` | Storage | | | ✓ | | ✓ |
| 6 | `addons/.../package-upload` | Storage | | | | ✓ | ✓ |
| 7 | `addons/.../alb/sg-alb` | Security | | | ✓ | | ✓ |
| 8 | `addons/.../sg-collibra-dq` | Security | | | ✓ | | ✓ |
| 9 | `database/rds-collibra-dq/sg-rds` | Security | | | ✓ | | ✓ |
| 10 | `database/rds-collibra-dq/rds` | Database | | | ✓ | | ✓ |
| 11 | `addons/collibra-dq-standalone` | Compute | | | ✓ | | ✓ |
| 12 | `addons/.../rotation-restart` | Ops | | | ✓ | | ✓ |
| 13 | `addons/.../alb` | Network | | | ✓ | | ✓ |
| 14 | `addons/.../alb/target-group-attachment` | Network | | | ✓ | | ✓ |

### Destroy order

Reverse of deploy. `destroy --target addon` removes steps 14–5. `destroy --target stack` removes 14–3. `destroy --target all` removes everything including bootstrap and shared bucket.

## Configuration reference

### Variables by deploy target

| Variable | bootstrap | stack | addon | package | full | Notes |
|----------|:---------:|:-----:|:-----:|:-------:|:----:|-------|
| `TF_VAR_environment` | ✓ | ✓ | ✓ | ✓ | ✓ | `dev` or `prod` |
| `TF_VAR_region` | ✓ | ✓ | ✓ | ✓ | ✓ | `eu-west-1`, `us-east-1`, `eu-central-1` |
| AWS credentials | ✓ | ✓ | ✓ | ✓ | ✓ | `AWS_PROFILE` or access key pair |
| `COLLIBRA_DQ_LICENSE_KEY` | | | ✓ | | ✓ | Required for app deploy |
| `COLLIBRA_DQ_ADMIN_PASSWORD` | | | opt | | opt | Auto-generated if unset/invalid |
| `COLLIBRA_DQ_AMI_ID` | | | auto | | auto | CLI auto-resolves RHEL 7.9 |
| `COLLIBRA_DQ_PACKAGE_FILENAME` | | | | ✓ | opt | Default: `dq-2025.11-SPARK356-JDK17-package-full.tar` |

Legend: ✓ = required, opt = optional override, auto = CLI auto-resolves

### Collibra runtime variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COLLIBRA_DQ_PACKAGE_URL` | auto | Override package S3 URL (auto-resolved from shared bucket) |
| `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK` | `false` | Enable ALB target auto-reconcile for direct standalone applies |
| `COLLIBRA_DQ_ENABLE_ROTATION_RESTART` | `true` | Enable EventBridge→SSM restart on secret rotation |
| `COLLIBRA_DQ_ENABLE_ROTATION_ALARMS` | `true` | Enable CloudWatch alarms for rotation failures |
| `COLLIBRA_DQ_ROTATION_ALARM_ACTIONS` | empty | Comma-separated alarm action ARNs (e.g. SNS topics) |
| `COLLIBRA_DQ_ROTATION_OK_ACTIONS` | empty | Comma-separated OK action ARNs |
| `COLLIBRA_DQ_RDS_PASSWORD_SSM_PARAMETER` | empty | SSM SecureString for RDS password (runtime fetch) |
| `COLLIBRA_DQ_ADMIN_PASSWORD_SSM_PARAMETER` | empty | SSM SecureString for admin password (runtime fetch) |
| `COLLIBRA_DQ_LICENSE_KEY_SSM_PARAMETER` | empty | SSM SecureString for license key (runtime fetch) |

### TG_* stack overrides

These drive naming, defaults, and cost topology in `env/stack/collibra-dq/root.hcl`.

| Variable | Dev default | Prod default | Description |
|----------|-------------|--------------|-------------|
| `TG_ORG` | `dq` | `dq` | Organization/name prefix |
| `TG_VPC_AZ_COUNT` | `2` | `3` | AZ count (clamped 2–3) |
| `TG_COLLIBRA_DQ_VPC_CIDR` | `10.11.0.0/16` | `10.21.0.0/16` | VPC CIDR block |
| `TG_SINGLE_NAT_GATEWAY` | `true` | `false` | NAT topology |
| `TG_ENABLE_FLOW_LOG` | `false` | `true` | VPC flow logs |
| `TG_RDS_INSTANCE_CLASS` | `db.t3.medium` | `db.t3.small` | DB instance class |
| `TG_RDS_MULTI_AZ` | `false` | `true` | RDS high availability |
| `TG_RDS_DELETION_PROTECTION` | `false` | `true` | DB deletion guard |
| `TG_COLLIBRA_DQ_INSTANCE_TYPE` | `m5.large` | `m5.xlarge` | EC2 instance type |
| `TG_ALB_DELETION_PROTECTION` | `false` | `true` | ALB deletion guard |
| `TG_EXPECTED_ACCOUNT_ID` | unset | unset | Safety check against wrong account |

### Collibra / Owl terminology

`Owl DQ` and `Collibra DQ` are equivalent. `OWL_BASE`/`OWL_HOME` refer to the same install directory. `METASTORE_USER`/`METASTORE_PASS` correspond to `OWL_METASTORE_USER`/`OWL_METASTORE_PASS`. All credential values are case-sensitive.

## Quick start

```bash
# 1. Clone and install
git clone <repository-url>
cd "AWS Classic Collibra Data Quality"
uv sync

# 2. Set required variables
export TF_VAR_environment=dev
export TF_VAR_region=eu-west-1
export AWS_PROFILE=my-profile
export COLLIBRA_DQ_LICENSE_KEY='<license-key>'

# 3. Deploy (package auto-uploads from packages/collibra-dq/ if missing)
uv run --no-editable python -m collibra_dq_starter.cli deploy --target full
```

`--no-editable` is recommended when project paths include spaces.

## Usage

### Command reference

```bash
# Help
uv run --no-editable python -m collibra_dq_starter.cli --help

# Full deploy
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full

# Infrastructure only (no app)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target stack

# App layer only (infra must exist)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target addon

# Package artifact only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target package

# Destroy app layer
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target addon

# Destroy everything
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target all --yes
```

### Target matrix

| Command | Target | What it does |
|---------|--------|--------------|
| `deploy` | `bootstrap` | State backend only (S3 + DynamoDB) |
| `deploy` | `stack` | Backend + core infra (VPC, endpoints) |
| `deploy` | `addon` | Backend + addon/app layers (SGs, RDS, EC2, ALB, ops) |
| `deploy` | `package` | Backend + package artifact module only |
| `deploy` | `full` | All of the above (auto-uploads package if missing) |
| `destroy` | `addon` | App + DB + ALB layers only |
| `destroy` | `package` | Package upload module only |
| `destroy` | `stack` | Addon + core infra, preserve backend + shared bucket |
| `destroy` | `all` | Everything including backend teardown |

### Artifact flow

Place the Collibra DQ installer `.tar` in `packages/collibra-dq/`. During `deploy --target full`, the CLI auto-uploads it to the shared artifact bucket if not already present. For explicit upload: `deploy --target package`. To upgrade: drop a new `.tar`, run `deploy --target package`, redeploy EC2.

## Prerequisites

| Tool | Purpose | Minimum version |
|------|---------|-----------------|
| `uv` | Python runtime + CLI | latest |
| `python` | CLI runtime | >= 3.10 |
| `terraform` | Infrastructure provisioning | >= 1.5.0 |
| `terragrunt` | Orchestration and dependencies | latest |
| `aws` CLI | AWS API access | v2.x |

AWS credentials must allow creation of VPC, EC2, RDS, S3, DynamoDB, ALB, IAM, and CloudWatch resources.

## Package contents

```
├── pyproject.toml                       # uv package + entrypoint
├── src/collibra_dq_starter/
│   ├── cli.py                           # argparse interface (dqctl)
│   ├── orchestrator.py                  # deploy/destroy orchestration
│   └── shell.py                         # subprocess wrapper
├── env/
│   ├── common.hcl                       # provider + backend generation
│   └── stack/collibra-dq/
│       ├── root.hcl                     # stack config, naming, env defaults
│       ├── bootstrap/                   # state backend (S3 + DynamoDB)
│       ├── shared/artifact-bucket/      # env-independent package storage
│       ├── network/
│       │   ├── vpc/                     # VPC + subnets + NAT
│       │   └── vpc-endpoints/           # SSM trio + S3 gateway
│       ├── database/rds-collibra-dq/
│       │   ├── sg-rds/                  # RDS security group
│       │   └── rds/                     # RDS PostgreSQL instance
│       └── addons/collibra-dq-standalone/
│           ├── install-script-bucket/   # per-env S3 bucket
│           ├── package-upload/          # artifact upload module
│           ├── sg-collibra-dq/          # EC2 security group
│           ├── (main)                   # EC2 instance + user-data
│           ├── rotation-restart/        # EventBridge + SSM + alarms
│           └── alb/
│               ├── sg-alb/             # ALB security group
│               ├── (main)             # ALB + listener + target group
│               └── target-group-attachment/
├── module/                              # reusable Terraform modules
│   ├── application/collibra-dq-standalone/
│   ├── database/rds/postgresql/
│   ├── network/vpc, alb, vpc-endpoints/
│   ├── security/security-group/ops, rds/
│   ├── storage/s3-package/
│   └── operations/secret-rotation-restart/
└── packages/collibra-dq/                # local installer artifact
```

## Operational runbook

### Preflight

```bash
aws sts get-caller-identity
uv run --no-editable python -m collibra_dq_starter.cli --help
```

### Verify target health after deploy

```bash
export REGION="eu-west-1"
export TG_ARN="<target-group-arn>"

aws elbv2 describe-target-health \
  --target-group-arn "$TG_ARN" \
  --region "$REGION" \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason]' \
  --output table
```

Expected: `initial` during startup, then `healthy` when DQ Web is listening on `:9000`.

### Verify ALB endpoint

```bash
export AWS_PAGER=""
ALB_DNS=$(cd env/stack/collibra-dq/addons/collibra-dq-standalone/alb && terragrunt output -raw load_balancer_dns_name)
curl -I "http://$ALB_DNS/"
```

Expected: HTTP 302 (redirect to `/login`) or 200. Use `http://` — default listener is HTTP only.

### SSM diagnostics

```bash
INSTANCE_ID=$(cd env/stack/collibra-dq/addons/collibra-dq-standalone && terragrunt output -raw instance_id)

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "cloud-init status --long || true",
    "cat /var/lib/collibra-dq-install/status.env || true",
    "systemctl status collibra-dq --no-pager -l || true",
    "ss -tlnp | egrep \"9000|9101\" || true",
    "tail -n 100 /var/log/collibra-dq-install.log || true"
  ]' \
  --query 'Command.CommandId' --output text)

sleep 5
aws ssm get-command-invocation \
  --region "$REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$INSTANCE_ID" \
  --output json
```

### Health-driven acceptance

Service health is the source of truth, not cloud-init status. Accept the environment as operational when all three are true:

1. ALB target health is `healthy`
2. Port 9000 is listening on the instance (`ss -tlnp`)
3. Local HTTP probe returns 200 or 302 (`curl http://127.0.0.1:9000/`)

If `status.env` shows `PHASE=HANDOFF` with a non-zero exit code but checks 1–3 are green, classify as a non-blocking bootstrap warning.

### Target re-attachment after instance replacement

When the EC2 instance is replaced, target-group attachment is handled automatically in orchestrated deploys. For direct standalone applies:

```bash
cd env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment
terragrunt apply --auto-approve
```

## Troubleshooting

### ALB returns 503

1. Check `describe-target-health` — empty means no target is registered (run target-group-attachment apply).
2. Target present but unhealthy — wait for install to complete, check SG rules and port 9000.
3. Target healthy — resolve ALB DNS and test `curl -I http://<dns>/` directly.

### Browser shows "refused to connect"

Default ALB listener is HTTP :80. Use `http://<alb-dns>/`, not `https://`.

### Package upload fails

Confirm the installer exists in `packages/collibra-dq/`. Check the filename matches `COLLIBRA_DQ_PACKAGE_FILENAME`.

### Rotation event did not trigger restart

Check EventBridge rule status in `addons/collibra-dq-standalone/rotation-restart`. Verify the instance is SSM-managed (`aws ssm describe-instance-information`). Inspect CloudWatch alarms for failures.

### State lock or backend mismatch

Confirm no concurrent apply/destroy is running. Use `TG_EXPECTED_ACCOUNT_ID` to guard against wrong-account deployment.

## Architecture decision records

### ADR-001: CLI-first orchestration

Deploy/destroy spans backend bootstrap, shared storage, network, database, compute, ALB, and post-deploy recovery. A Python CLI centralizes retry behavior, bucket purge fallback, bootstrap recovery, and environment validation. Direct Terragrunt remains possible for debugging but is not the primary operating model.

### ADR-002: Environment-driven configuration

All runtime config is injected via environment variables (`TF_VAR_*`, `TG_*`, `COLLIBRA_DQ_*`). No static env catalogs, no per-client branch divergence.

### ADR-003: Stack-scoped state backend

Dedicated S3 + DynamoDB per stack/environment isolates failure domains. Bootstrap must be created first; full destroy handles backend deletion as a special case with digest retry.

### ADR-004: Shared artifact bucket + per-env install script

The large package artifact is env-agnostic (upload once). The rendered install script contains env-specific secrets and lives in a separate per-env bucket.

### ADR-005: EC2 in public subnet

The EC2 Collibra DQ instance is deployed into a public subnet in AZ-a alongside the ALB. RDS PostgreSQL runs in a private subnet in AZ-b, accessible only via `sg-rds` which permits ingress from `sg-collibra-dq`. VPC endpoints in private subnets handle SSM and S3 traffic.

### ADR-006: Subnet layout and AZ distribution

`/22` subnets provide 1024 IPs each — large enough for operational headroom, small enough to fit 6 subnets in a `/16`. Dev uses 2 AZs (minimum for ALB + RDS), prod uses 3 for resilience. `cidrsubnet(cidr, 6, index)` generates subnets deterministically.

### ADR-007: Cost-optimized dev defaults

Dev defaults: 2 AZs, single NAT gateway, single-AZ RDS, `m5.large` EC2, no flow logs, no deletion protection. Not equivalent to prod HA posture.

### ADR-008: HTTP-only ALB by default

HTTPS requires ACM certificate and domain decisions. HTTP removes that dependency from baseline deployment.

### ADR-009: Direct standalone hook is opt-in

The ALB target re-attachment after-hook (`COLLIBRA_DQ_ENABLE_STANDALONE_HOOK`) is disabled by default. Full deploy already owns target-group-attachment in module order.

### ADR-010: Service health over bootstrap status

Runtime service signals (ALB target health, port listener, HTTP probe) are the source of truth, not cloud-init exit codes.

## Security notes

1. Terraform state can contain sensitive data — protect backend access with IAM.
2. Never commit secrets into repo files.
3. Prefer SSM Parameter Store (SecureString) for runtime secrets over embedding values in install scripts.
4. EC2 runs in a public subnet but ingress is controlled by `sg-collibra-dq` — only the ALB can reach port 9000.
5. RDS runs in a private subnet with no public accessibility.
6. VPC endpoints keep SSM and S3 traffic off the public internet.
7. Enable `TG_RDS_DELETION_PROTECTION`, `TG_RDS_MULTI_AZ`, and TLS/ACM for production.
8. Set `TG_EXPECTED_ACCOUNT_ID` in CI/CD to prevent cross-account misfire.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching strategy, commit conventions, and release checklist.

## Additional documentation

| Document | Description |
|----------|-------------|
| `collibra-dq-architecture.drawio` | Architecture diagrams (network topology + operations flow) |
| [env/README.md](env/README.md) | Terragrunt directory overview |
| [env/stack/README.md](env/stack/README.md) | Live stack map and lifecycle |
| [env/stack/collibra-dq/README.md](env/stack/collibra-dq/README.md) | Stack-specific details and ADRs |
| [module/application/collibra-dq-standalone/README.md](module/application/collibra-dq-standalone/README.md) | Standalone module behavior and startup |
| [packages/README.md](packages/README.md) | Installer package guide |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Process and release guidance |