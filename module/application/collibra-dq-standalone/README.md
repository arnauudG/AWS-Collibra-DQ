# Collibra DQ Standalone Module

Creates an EC2 instance running Collibra Data Quality as a standalone installation.

## Description

This module deploys Collibra DQ (Owl DQ) on a single EC2 instance with:

- CentOS/RHEL 7 compatible EC2 instance
- Automatic Collibra DQ installation via user data script
- Apache Spark for data processing
- PostgreSQL connectivity to RDS metastore
- IAM role with SSM and S3 access
- Optional runtime secret resolution via SSM Parameter Store (non-breaking fallback to direct values)
- IMDSv2 enforced for security
- Runtime guard that fails installation on non-CentOS/RHEL 7 hosts

## Usage

```hcl
module "collibra_dq" {
  source = "../../../module/application/collibra-dq-standalone"

  name          = "acme-dev-collibra-dq"
  region        = "eu-west-1"
  instance_type = "m5.xlarge"

  vpc_security_group_ids = [dependency.sg_collibra_dq.outputs.security_group_id]
  subnet_id              = dependency.vpc.outputs.private_subnets[0]

  iam_role_name = "acme-dev-collibra-dq-role"

  # PostgreSQL (RDS) connection
  postgresql_host     = dependency.rds.outputs.db_instance_address
  postgresql_port     = 5432
  postgresql_database = "collibra_dq"
  owl_metastore_user       = dependency.rds.outputs.db_instance_username
  owl_metastore_secret_arn = dependency.rds.outputs.master_user_secret_arn
  # Optional runtime secret retrieval from SSM (preferred)
  # owl_metastore_pass_ssm_parameter = "/acme/dev/collibra/rds-password"

  # Collibra DQ configuration
  # UI login uses the built-in username "admin".
  # If dq_admin_user_password is empty, installer generates a compliant password.
  dq_admin_user_password = var.COLLIBRA_DQ_ADMIN_PASSWORD
  license_key           = var.COLLIBRA_DQ_LICENSE_KEY
  # Optional runtime secret retrieval from SSM (preferred)
  # dq_admin_user_password_ssm_parameter = "/acme/dev/collibra/admin-password"
  # license_key_ssm_parameter            = "/acme/dev/collibra/license-key"

  root_block_device = {
    volume_size = 100
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Environment = "dev"
    Project     = "Collibra-DQ"
  }
}
```

## Required Inputs

| Name | Description | Type |
|------|-------------|------|
| `name` | Name of the EC2 instance | `string` |
| `region` | AWS region | `string` |
| `instance_type` | EC2 instance type | `string` |
| `vpc_security_group_ids` | List of security group IDs | `list(string)` |
| `subnet_id` | Subnet ID for the instance | `string` |
| `iam_role_name` | IAM role name for the instance | `string` |
| `postgresql_host` | PostgreSQL host (RDS endpoint) | `string` |
| `owl_metastore_user` | PostgreSQL username for DQ metastore (case-sensitive) | `string` |
| `license_key` | Collibra DQ license key | `string` |

## Optional Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `ami` | AMI ID (recommended default path for restricted accounts) | `string` | `null` |
| `owl_base` | Base directory for Collibra DQ installation (`OWL_BASE` / `OWL_HOME`) | `string` | `"/opt/collibra-dq"` |
| `owl_metastore_pass` | PostgreSQL password for DQ metastore (case-sensitive; optional when using managed secret) | `string` | `""` |
| `postgresql_port` | PostgreSQL port | `number` | `5432` |
| `postgresql_database` | PostgreSQL database name | `string` | `"dqMetastore"` |
| `spark_package` | Spark package filename | `string` | `"spark-3.5.6-bin-hadoop3.tgz"` |
| `dq_admin_user_password` | Password for DQ Web built-in admin user `admin` (case-sensitive). For bootstrap compatibility it must be 8-72 chars, use only letters/digits/underscore, include upper/lower/digit/underscore, and must not contain `admin`; if empty/invalid, installer auto-generates a compliant value | `string` | `""` |
| `dq_package_url` | Signed link/URL to full Collibra DQ package | `string` | `""` |
| `dq_package_filename` | Filename of the DQ package | `string` | `"dq-full-package.tar.gz"` |
| `license_name` | Collibra DQ license name | `string` | `""` |
| `owl_metastore_pass_ssm_parameter` | SSM SecureString parameter name for metastore password (runtime fetch on EC2) | `string` | `""` |
| `owl_metastore_secret_arn` | Secrets Manager ARN for RDS master secret (runtime fetch on EC2) | `string` | `""` |
| `dq_admin_user_password_ssm_parameter` | SSM SecureString parameter name for admin password (runtime fetch on EC2) | `string` | `""` |
| `license_key_ssm_parameter` | SSM SecureString parameter name for license key (runtime fetch on EC2) | `string` | `""` |
| `license_name_ssm_parameter` | SSM SecureString parameter name for license name (runtime fetch on EC2) | `string` | `""` |
| `root_block_device` | Root block device configuration | `object` | `null` |
| `ebs_optimized` | Enable EBS optimization | `bool` | `false` |
| `monitoring` | Enable detailed monitoring | `bool` | `true` |
| `associate_public_ip_address` | Associate public IP address | `bool` | `false` |
| `metadata_options` | Instance metadata options | `object` | IMDSv2 enforced |
| `tags` | Tags to apply to resources | `map(string)` | `{}` |

Admin credential lifecycle:
- `dq_admin_user_password` seeds the built-in UI user `admin` only on the first successful install against a fresh Collibra DQ metastore.
- Re-running the standalone deploy against an already-existing metastore does not reset the existing admin password stored in the database.
- If the metastore is destroyed and recreated, the admin password is seeded again from the current Terraform input value.

## Outputs

| Name | Description |
|------|-------------|
| `instance_id` | EC2 instance ID |
| `instance_arn` | EC2 instance ARN |
| `instance_public_ip` | Public IP address (if applicable) |
| `instance_private_ip` | Private IP address |
| `iam_role_name` | IAM role name |
| `iam_role_arn` | IAM role ARN |
| `owl_base` | Collibra DQ installation directory |
| `dq_web_url` | URL to access DQ Web |

## Security Considerations

- Prod: instance is deployed in a private subnet (no public IP). Dev: public subnet by default for cost savings (override with `TG_COLLIBRA_DQ_PUBLIC_SUBNET=false`)
- Access via Application Load Balancer (HTTP by default; HTTPS requires ACM + listener config)
- IMDSv2 is enforced (http_tokens = "required")
- Storage is encrypted at rest
- SSM Session Manager for administrative access (no SSH)
- Direct secrets are marked sensitive when passed as variables
- Prefer runtime SSM parameters so secret values are not embedded in rendered install scripts

## Cost Implications

| Resource | Dev (m5.large) | Prod (m5.xlarge) |
|----------|----------------|------------------|
| EC2 Instance (On-Demand) | ~$70/month | ~$140/month |
| EBS Volume (100GB gp3) | ~$8/month | ~$8/month |
| Data Transfer | Variable | Variable |

**Instance Type Defaults (from `root.hcl`):**
- **Dev**: m5.large (2 vCPU, 8GB RAM)
- **Prod**: m5.xlarge (4 vCPU, 16GB RAM)
- Override with `TG_COLLIBRA_DQ_INSTANCE_TYPE`

## Dependencies

- `network/vpc` - VPC and private subnets
- `security/security-group/collibra-dq` - Security group for the instance
- `database/rds/postgresql` - PostgreSQL database for metastore
- Package artifact URL (`dq_package_url`) - can be sourced from `storage/s3-package` module or external artifact storage

## Dependent Modules

- `network/alb/application` - Application Load Balancer for HTTPS access
- `network/alb/target-group-attachment` - Registers instance with ALB

## Installation Process

The module uses a user data script that:

1. Updates system packages
2. Installs Java 17 and required dependencies
3. Downloads and installs Apache Spark
4. Downloads Collibra DQ package from S3
5. Configures PostgreSQL connection
6. Activates Collibra DQ license
7. Starts DQ Web and Agent services

Notes:

- Owl and Collibra naming are equivalent in scripts and environment variables.
- `OWL_HOME` is exported as the same path as `OWL_BASE`.
- `METASTORE_USER`/`METASTORE_PASS` aliases are exported alongside `OWL_METASTORE_USER`/`OWL_METASTORE_PASS`.
- Username and password are treated as case-sensitive.
- License activation requires `license_key`; expiration date is not required.
- Runtime hooks refresh the latest RDS secret and validate DB auth before each service start.
- DB auth verification is non-blocking by default during bootstrap/start to avoid false failures caused by legacy `psql` clients on RHEL 7.
- Strict DB auth gating can be enabled by setting `COLLIBRA_VERIFY_RDS_STRICT=1` in the runtime environment before executing the verification helper.
- Event-driven restarts on secret rotation are managed by `operations/secret-rotation-restart`.

**Installation logs**: `/var/log/collibra-dq-install.log`

### Post-deploy checks

Use these checks to confirm service readiness:

- ALB target health is `healthy`
- Port `9000` is listening on the instance
- HTTP probe on `http://127.0.0.1:9000/` returns `200` or `302`

If `cloud-init` reports `scripts-user` failure but the checks above are green, treat the deployment as operational and inspect logs for non-blocking bootstrap warnings.

### Bootstrap handoff behavior

The bootstrap launcher (`bootstrap_install.sh.tmpl`) runs the full installer and persists status to:

- `/var/lib/collibra-dq-install/status.env`
- `/var/log/collibra-dq-install.log`

Bootstrap phase semantics:

- `BOOTSTRAP`: preflight and AWS CLI/SSM readiness.
- `PACKAGE_DOWNLOAD`: install script retrieval from S3.
- `HANDOFF`: detached installer execution and wait.

During `HANDOFF`, non-zero installer exits can happen even when the DQ web process becomes available shortly after.
Bootstrap now waits for a listener on `:9000` before deciding failure, which reduces false negatives.

Operational precedence:

1. ALB target health.
2. listener on `*:9000`.
3. local HTTP result (`200` or `302`).
4. cloud-init final state and `status.env`.

If checks 1-3 are healthy, treat `PHASE=HANDOFF` with non-zero `LAST_EXIT_CODE` as non-blocking.

Related stack behavior:

- direct apply on `env/stack/collibra-dq/addons/collibra-dq-standalone` auto-reconciles
  ALB target attachment through a Terragrunt `after_hook`.

## Accessing Collibra DQ

After deployment:

1. **Via ALB (Recommended)**: Access through the Application Load Balancer URL
2. **Via SSM**: Use AWS Systems Manager Session Manager
   ```bash
   aws ssm start-session --target <instance-id>
   ```

3. **Service URLs** (on instance):
   - DQ Web: http://localhost:9000
   - DQ Agent Health: http://localhost:9101
   - Spark Master UI: http://localhost:8080
