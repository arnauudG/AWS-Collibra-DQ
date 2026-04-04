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
- `TG_COLLIBRA_DQ_PUBLIC_SUBNET` (defaults: `true` in dev, always `false` in prod; places EC2 in public subnet and disables NAT Gateway + interface VPC endpoints, saving ~$55/mo)
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
- In dev (default), EC2 runs in a public subnet to avoid NAT Gateway and interface VPC endpoint costs. SG rules still restrict ingress to ALB-only. Set `TG_COLLIBRA_DQ_PUBLIC_SUBNET=false` to use private subnet instead.

## Verification Runbook

Collibra DQ UI login uses the built-in username `admin`. Do not attempt to sign in with the setup email value persisted on the instance.

Credential lifecycle:
- The password supplied through `COLLIBRA_DQ_ADMIN_PASSWORD` is only guaranteed during the first successful install against a fresh metastore.
- Re-running `deploy --target addon` against an already-existing environment does not reset the existing UI admin account because the same RDS metastore is reused.
- `destroy --target addon` followed by `deploy --target addon` recreates the RDS metastore in the current orchestrator ordering, so it should reseed the admin account from current inputs.
- `destroy --target all` followed by `deploy --target full` is still the clearest full-environment rebuild path.
- A vendor quirk in the packaged `setup.sh` exports the encrypted admin password into `owl-env.sh`; this stack overrides that file after setup so `owl-web` receives the raw bootstrap password and can create the `admin` user.

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

Retrieve the effective UI credentials directly from the instance:

```bash
export REGION="${TF_VAR_region:-eu-west-1}"
cd env/stack/collibra-dq/addons/collibra-dq-standalone
export INSTANCE_ID="$(terragrunt output -raw instance_id)"

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["bash -lc '\''eval \"$(grep \"^export DQ_ADMIN_UI_USERNAME=\" /etc/profile.d/collibra-dq.sh)\"; eval \"$(grep \"^export DQ_ADMIN_USER_PASSWORD=\" /etc/profile.d/collibra-dq.sh)\"; printf \"LOGIN_USER=%s\nLOGIN_PASSWORD=%s\n\" \"$DQ_ADMIN_UI_USERNAME\" \"$DQ_ADMIN_USER_PASSWORD\"'\''"]' \
  --query "Command.CommandId" \
  --output text)

sleep 3

aws ssm get-command-invocation \
  --region "$REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$INSTANCE_ID" \
  --query 'StandardOutputContent' \
  --output text
```

If a fresh rebuild still fails to authenticate, inspect the admin bootstrap debug file and setup log:

```bash
export REGION="${TF_VAR_region:-eu-west-1}"
cd env/stack/collibra-dq/addons/collibra-dq-standalone
export INSTANCE_ID="$(terragrunt output -raw instance_id)"

CMD_ID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["bash -lc '\''echo \"--- /etc/collibra-dq/admin-bootstrap-debug.env ---\"; cat /etc/collibra-dq/admin-bootstrap-debug.env; echo; echo \"--- tail -n 120 /var/log/collibra-dq-setup.log ---\"; tail -n 120 /var/log/collibra-dq-setup.log'\''"]' \
  --query "Command.CommandId" \
  --output text)

sleep 3

aws ssm get-command-invocation \
  --region "$REGION" \
  --command-id "$CMD_ID" \
  --instance-id "$INSTANCE_ID" \
  --query 'StandardOutputContent' \
  --output text
```

Interpretation:
- `DQ_ADMIN_PASSWORD_SOURCE=provided` means the input password passed installer validation and was handed to Collibra setup.
- `generated-empty` or `generated-invalid` means the installer replaced the requested password before setup.
- Review the setup log tail for any Collibra-side rejection or lockout-related messages.

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

Detailed ADRs live in [docs/adr/README.md](../../../docs/adr/README.md).

- [ADR-C1](../../../docs/adr/ADR-C1-standalone-ec2-deployment-model.md): keep the current standalone EC2 deployment model.
- [ADR-C2](../../../docs/adr/ADR-C2-shared-package-and-env-script.md): separate reusable package artifacts from env-specific rendered scripts.
- [ADR-C3](../../../docs/adr/ADR-C3-http-first-ingress.md): keep HTTP as the default ingress path.
- [ADR-C4](../../../docs/adr/ADR-C4-health-driven-acceptance.md): accept runtime health over bootstrap exit state.

## Related Docs

- Root product guide: [README.md](../../../README.md)
- Stack overview: [env/stack/README.md](../README.md)
- ADR catalog: [docs/adr/README.md](../../../docs/adr/README.md)
- Testing strategy: [docs/testing-strategy.md](../../../docs/testing-strategy.md)
- Package artifact details: [packages/collibra-dq/README.md](../../../packages/collibra-dq/README.md)
