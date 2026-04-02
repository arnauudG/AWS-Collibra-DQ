# Collibra DQ Stack

Live Terragrunt stack for deploying Collibra DQ on AWS as a standalone EC2 workload with ALB ingress and RDS PostgreSQL backend.

## Product Intent (PRD)

This stack exists to provide a deployable Collibra DQ environment that is:

- reproducible across environments
- low-touch for dev operators
- explicit about runtime dependencies
- operable through ALB + SSM without SSH dependency

Primary user:
- platform engineer or DevOps engineer responsible for provisioning and operating a Collibra DQ environment

Primary outcome:
- one command to deploy the full stack and one command to destroy it cleanly

## Platform Design (PSD)

The stack is intentionally layered:

- backend first (`bootstrap`)
- shared storage second (`shared/artifact-bucket`)
- network before dependent services
- database before application runtime
- ALB before target registration

Traffic flow:

- browser -> ALB (`:80` by default)
- ALB -> EC2 Collibra DQ (`:9000`)
- EC2 -> RDS PostgreSQL (`:5432`)
- EC2 -> S3 via IAM role and VPC endpoints

## Module Layout

- `bootstrap`
- `shared/artifact-bucket` (env-independent, holds DQ package)
- `network/vpc`
- `network/vpc-endpoints`
- `database/rds-collibra-dq/sg-rds`
- `database/rds-collibra-dq/rds`
- `addons/collibra-dq-standalone/install-script-bucket` (per-env, holds rendered install script)
- `addons/collibra-dq-standalone/package-upload` (uploads to shared artifact bucket)
- `addons/collibra-dq-standalone/sg-collibra-dq`
- `addons/collibra-dq-standalone`
- `addons/collibra-dq-standalone/rotation-restart`
- `addons/collibra-dq-standalone/alb/sg-alb`
- `addons/collibra-dq-standalone/alb`
- `addons/collibra-dq-standalone/alb/target-group-attachment`

## Execution Model

Use the CLI from repo root:

```bash
# backend only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target bootstrap

# backend + core infrastructure
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target stack

# package artifact only (independent lifecycle)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target package

# full stack
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full
```

Destroy lifecycle:

```bash
# addons only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target addon

# package artifact only
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target package

# addons + infra, keep backend
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target stack

# full teardown including backend
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target all
```

## Runtime Variables (Stack-Specific)

Common variables are documented in root `README.md`. Stack-specific variables to be aware of:

- `TG_VPC_AZ_COUNT` (defaults: `2` in dev, `3` in prod; clamped to 2-3)
- `COLLIBRA_DQ_PACKAGE_FILENAME`
- `COLLIBRA_DQ_PACKAGE_URL` (optional override; otherwise resolved automatically from shared artifact bucket)
- `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK` (optional; default `false`; only for direct standalone apply flows)
- `COLLIBRA_DQ_SKIP_PACKAGE_UPLOAD`
- `COLLIBRA_DQ_ENABLE_S3_ACCELERATION`
- `COLLIBRA_DQ_ENABLE_ROTATION_RESTART`
- `COLLIBRA_DQ_ENABLE_ROTATION_ALARMS`
- `COLLIBRA_DQ_ROTATION_ALARM_ACTIONS`
- `COLLIBRA_DQ_ROTATION_OK_ACTIONS`
- `COLLIBRA_DQ_RDS_PASSWORD_SSM_PARAMETER`
- `COLLIBRA_DQ_ADMIN_PASSWORD_SSM_PARAMETER`
- `COLLIBRA_DQ_LICENSE_KEY_SSM_PARAMETER`
- `COLLIBRA_DQ_LICENSE_NAME_SSM_PARAMETER`

## ALB Behavior

- ALB is internet-facing but HTTP-only by default (`:80`).
- Traffic is forwarded to EC2 on port `9000`.
- Health checks use `traffic-port` with matcher `200-499`.
- Temporary unhealthy targets are expected while initial Collibra install completes.
- Because ALB and RDS both require multi-subnet placement, the minimum valid footprint is 2 public + 2 private subnets.

## Verification Runbook

Retrieve ALB DNS:

```bash
cd env/stack/collibra-dq/addons/collibra-dq-standalone/alb
terragrunt output -raw load_balancer_dns_name
```

Inspect target group health:

```bash
cd env/stack/collibra-dq/addons/collibra-dq-standalone/alb
terragrunt output -json target_group_arns
aws elbv2 describe-target-health --target-group-arn "<tg-arn>" --region "$TF_VAR_region"
```

If target health output is empty, register the latest EC2 target:

```bash
cd env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment
terragrunt apply --auto-approve
```

If `addons/collibra-dq-standalone` was replaced:

- full orchestrated deploy handles target-group-attachment via module order
- direct standalone-only apply can use the after-hook when explicitly enabled with `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true`

Use the command below as fallback when needed.

### Post-replacement critical sequence (fallback)

When `addons/collibra-dq-standalone` shows `Plan: 1 to add, 0 to change, 1 to destroy`, run this exact sequence:

```bash
export REGION="eu-west-1"
export TG_ARN="<target-group-arn>"

cd env/stack/collibra-dq/addons/collibra-dq-standalone
export INSTANCE_ID="$(terragrunt output -raw instance_id)"
echo "$INSTANCE_ID"

cd alb/target-group-attachment
terragrunt apply --auto-approve

aws elbv2 describe-target-health \
  --region "$REGION" \
  --target-group-arn "$TG_ARN" \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason,TargetHealth.Description]' \
  --output table
```

Expected result: latest `INSTANCE_ID` appears and moves to `healthy`.

### 503 triage decision path

1. `describe-target-health` empty:
   target not attached; run target-group-attachment apply.
2. target present but not `healthy`:
   wait and re-check app listener/logs.
3. target `healthy` and ALB still failing:
   resolve ALB DNS and test `curl -I` directly.

```bash
export AWS_PAGER=""

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

Expected: HTTP `302` or `200`.

If browser shows "refused to connect", verify you are using `http://` (not `https://`) for the default ALB listener configuration.

### Runtime diagnostics via SSM

```bash
export REGION="$TF_VAR_region"
export INSTANCE_ID="$(cd env/stack/collibra-dq/addons/collibra-dq-standalone && terragrunt output -raw instance_id)"

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "cloud-init status --long || true",
    "cat /var/lib/collibra-dq-install/status.env || true",
    "systemctl status cloud-final --no-pager -l || true",
    "ss -tlnp | egrep \"9000|9101\" || true",
    "curl -sS -o /dev/null -w \"%{http_code}\\n\" http://127.0.0.1:9000/ || true",
    "tail -n 200 /var/log/collibra-dq-install.log || true"
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

### Interpreting `PHASE=HANDOFF` and non-zero `LAST_EXIT_CODE`

This stack can report `PHASE=HANDOFF` with `LAST_EXIT_CODE=1` or `2` in `status.env` while the service is already usable.

Use this acceptance criteria for operational success:

- target health is `healthy`
- listener exists on `*:9000`
- local probe `curl http://127.0.0.1:9000/` returns `200` or `302`

If all three are true, treat cloud-init bootstrap failure as non-blocking and continue.

## Operational Notes

- EC2 host is private by default; admin access is through SSM Session Manager.
- Package upload can take significant time due to artifact size.
- App deployment (`deploy --target full`) auto-uploads the package from `packages/collibra-dq/` to the shared artifact bucket if missing. Override with `COLLIBRA_DQ_PACKAGE_URL`.
- Keep `TG_EXPECTED_ACCOUNT_ID` set in CI/CD to avoid accidental deployment to wrong AWS account.
- Rotation restart addon listens for secret rotation events and restarts `collibra-dq` through SSM.
- Runtime pre-start hooks refresh secret + verify DB auth before service start.
- DB auth verification is non-blocking by default for compatibility with legacy RHEL 7 PostgreSQL clients.
- Dev defaults are cost-oriented: 1 VPC, 2 AZs, single NAT gateway, single-AZ RDS.

## Architecture Decision Records (ADR)

### ADR-C1: Standalone EC2 deployment model

Decision:
Deploy Collibra DQ as a single standalone EC2 workload instead of introducing container orchestration.

Reason:
This matches the current product packaging and keeps the platform operationally simple.

Consequence:
- Scaling and HA are limited compared to distributed/containerized models

### ADR-C2: Shared package artifact, env-specific rendered script

Decision:
Store the heavy package once in shared artifact storage, but keep rendered install bootstrap script per environment.

Reason:
The package is reusable, but the rendered script contains environment-specific runtime values.

Consequence:
- Shared artifact lifecycle differs from env-specific install-script lifecycle

### ADR-C3: HTTP-first ingress

Decision:
Expose default ingress on HTTP only.

Reason:
Certificate management should not block baseline environment deployment.

Consequence:
- Operators must use `http://<alb-dns>/` in the default stack
- HTTPS must be added intentionally later

### ADR-C4: Health-driven acceptance

Decision:
Accept the environment as operational based on ALB target health and local app readiness rather than cloud-init success alone.

Reason:
Bootstrap can report non-zero exit state even when the service is usable.

Consequence:
- Runbooks and troubleshooting prioritize service health over bootstrap status files

## Related Docs

- Root product guide: [README.md](../../../README.md)
- Stack overview: [env/stack/README.md](../README.md)
- Package artifact details: [packages/collibra-dq/README.md](../../../packages/collibra-dq/README.md)
