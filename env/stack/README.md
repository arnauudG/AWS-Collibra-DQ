# Live Stack (`env/stack/`)

This folder contains live Terragrunt stack configuration used by the Collibra DQ starter.

## Intent

This README is the operator view of the live stack layout.

Use it to understand:

- what each stack folder owns
- in which order modules are expected to run
- where to intervene during targeted repair

For product-level context, start with the root [README.md](../README.md).

## PRD Summary

The live stack is designed to satisfy three operator requirements:

- predictable deployment order
- low-friction teardown and rebuild in dev
- clear ownership boundaries between backend, shared artifacts, network, database, and app layers

## PSD Summary

The stack is split into lifecycle domains:

- `bootstrap`: Terraform backend
- `shared`: reusable artifacts
- `network`: foundational networking
- `database`: RDS and database-facing security
- `addons`: app/runtime-facing components

## Stack Inventory

### `collibra-dq/root.hcl`

Defines stack-wide behavior:

- remote state naming (`S3` + `DynamoDB`)
- shared tags
- dynamic defaults by environment (`dev`/`prod`)
- reusable client-level overrides via `TG_*`
- cost defaults (`dev`: 2 AZ footprint + single-AZ RDS)

### `collibra-dq/bootstrap`

Terraform backend resources:

- tfstate bucket
- state lock table

### `collibra-dq/network`

- `vpc`
- `vpc-endpoints`

### `collibra-dq/database`

- `rds-collibra-dq/sg-rds`
- `rds-collibra-dq/rds`

### `collibra-dq/shared`

- `artifact-bucket` (env-independent S3 bucket for DQ package artifacts)

### `collibra-dq/addons`

- `collibra-dq-standalone/install-script-bucket` (per-env S3 bucket for rendered install script)
- `collibra-dq-standalone/package-upload` (uploads package to shared artifact bucket)
- `collibra-dq-standalone/sg-collibra-dq`
- `collibra-dq-standalone` (EC2 app host)
- `collibra-dq-standalone/rotation-restart`
- `collibra-dq-standalone/alb/sg-alb`
- `collibra-dq-standalone/alb`
- `collibra-dq-standalone/alb/target-group-attachment`

## Lifecycle Execution

Preferred execution path is CLI-driven from repo root:

```bash
# package artifact deploy (independent)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target package

# full deploy
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full

# full teardown
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target all
```

The orchestrator enforces deterministic module order and non-interactive terragrunt execution.

## Direct Module Operations (Advanced)

Use direct terragrunt commands only for targeted debugging:

```bash
cd env/stack/collibra-dq/network/vpc
terragrunt plan --non-interactive
terragrunt apply --non-interactive
```

For standard operations, prefer the CLI so dependency order and safety checks remain consistent.

## ADR Summary

### ADR-S1: Lifecycle domains are separated by ownership

Decision:
Keep backend, shared artifacts, infra, and app addons in separate folders and separate Terragrunt roots.

Reason:
This supports selective deploy/destroy and limits blast radius during repairs.

### ADR-S2: Orchestrated CLI is the default operating model

Decision:
Document direct Terragrunt as advanced-only and make CLI-driven operation the default path.

Reason:
The CLI carries recovery logic that raw Terragrunt does not.

### ADR-S3: Full deploy owns attachment ordering

Decision:
Treat `alb/target-group-attachment` as an explicit lifecycle step in orchestrated deploy rather than relying solely on local hooks.

Reason:
This avoids race conditions between EC2 and ALB output availability.

## Recovery Runbook (Direct Terragrunt)

Use this only when targeted repair is required.

### Replace standalone instance

```bash
export COLLIBRA_DQ_AMI_ID=<rhel-7.9-ami-id>

cd "env/stack/collibra-dq/addons/collibra-dq-standalone"
terragrunt apply --auto-approve --replace='module.ec2.aws_instance.this[0]'
```

### Re-attach ALB target after replacement

```bash
cd "env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment"
terragrunt apply --auto-approve
```

### Verify target health

```bash
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn> \
  --region <region> \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason,TargetHealth.Description]' \
  --output table
```

Interpretation:

- Empty output means no registered targets.
- `initial` is expected during startup.
- `healthy` is required for traffic readiness.

### End-to-end ALB verification

```bash
export AWS_PAGER=""
export REGION="<region>"
export TG_ARN="<target-group-arn>"

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

Expected response code is typically `302` (redirect to `/login`) or `200`.

### Known bootstrap status behavior

`/var/lib/collibra-dq-install/status.env` can report `PHASE=HANDOFF` with non-zero `LAST_EXIT_CODE` even when DQ is already serving traffic.

Treat deployment as operational when all of these are true:

- target health is `healthy`
- instance is listening on `*:9000`
- local `curl http://127.0.0.1:9000/` returns `200` or `302`

In that case, classify cloud-init status as a non-blocking warning and continue operations.

### Standalone replacement and target sync

Any replacement of `addons/collibra-dq-standalone` changes the EC2 instance ID.
Target-group attachment is handled in ordered module execution for orchestrated full deploy.
For direct standalone-only applies, hook-based auto-reconcile is opt-in with:

```bash
export COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true
```

Use this fallback if the hook is skipped, interrupted, or disabled:

```bash
cd "env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment"
terragrunt apply --auto-approve
```

Without target sync, ALB can return `503` because no current target is attached.

### ALB endpoint protocol

Default ALB listener is HTTP only (`:80`). Use:

```bash
http://<alb-dns>/
```

If you browse to `https://<alb-dns>/` without adding an HTTPS listener + ACM certificate, browser-level connection errors are expected.

## SSM Diagnostics (Copy/Paste)

```bash
export REGION="<region>"
export INSTANCE_ID="$(cd "env/stack/collibra-dq/addons/collibra-dq-standalone" && terragrunt output -raw instance_id)"

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
