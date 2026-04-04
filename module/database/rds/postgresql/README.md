# RDS PostgreSQL Module

Creates an Amazon RDS PostgreSQL instance with security best practices.

## Description

This module creates a PostgreSQL RDS instance configured for Collibra DQ. It includes:

- PostgreSQL database instance
- DB subnet group for VPC placement
- Managed custom DB parameter group
- VPC-suffixed subnet/parameter group names to avoid collisions with pre-existing resources in the same AWS account/region
- VPC-suffixed DB identifier to avoid collisions with legacy instances created in another VPC
- AWS Secrets Manager-managed master password (default)
- Optional static/random password mode (legacy)
- Stable final snapshot naming (no timestamp plan churn)
- Storage encryption at rest
- CloudWatch logs export
- Performance Insights (optional)

## Usage

```hcl
module "rds" {
  source = "../../../module/database/rds/postgresql"

  name               = "acme-dev-collibra-dq-rds"
  vpc_id             = dependency.vpc.outputs.vpc_id
  subnet_ids         = dependency.vpc.outputs.private_subnets
  security_group_ids = [dependency.sg_rds.outputs.security_group_id]

  engine_version      = "15.4"
  instance_class      = "db.t3.medium"
  allocated_storage   = 100
  max_allocated_storage = 200

  database_name   = "collibra_dq"
  master_username = "collibra_dq_admin"

  backup_retention_period = 7
  multi_az               = false  # true for production

  tags = {
    Environment = "dev"
    Project     = "Collibra-DQ"
  }
}
```

## Required Inputs

| Name | Description | Type |
|------|-------------|------|
| `name` | Name prefix for RDS instance and related resources | `string` |
| `vpc_id` | VPC ID where RDS will be deployed | `string` |
| `subnet_ids` | List of private subnet IDs for RDS subnet group | `list(string)` |
| `security_group_ids` | List of security group IDs to attach to RDS | `list(string)` |

## Optional Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `engine_version` | PostgreSQL engine version | `string` | `"15.4"` |
| `instance_class` | RDS instance class | `string` | `"db.t3.medium"` |
| `allocated_storage` | Initial allocated storage in GB | `number` | `100` |
| `max_allocated_storage` | Maximum allocated storage for autoscaling | `number` | `200` |
| `storage_type` | Storage type (gp3, gp2, io1) | `string` | `"gp3"` |
| `storage_encrypted` | Enable storage encryption | `bool` | `true` |
| `database_name` | Name of the default database | `string` | `"collibra_dq"` |
| `master_username` | Master username for RDS | `string` | `"collibra_dq_admin"` |
| `master_password` | Master password (generated if not provided) | `string` | `""` |
| `manage_master_user_password` | Use RDS-managed Secrets Manager master password | `bool` | `true` |
| `create_random_password` | Create random password if not provided | `bool` | `true` |
| `backup_retention_period` | Number of days to retain backups | `number` | `7` |
| `backup_window` | Preferred backup window (UTC) | `string` | `"03:00-04:00"` |
| `maintenance_window` | Preferred maintenance window (UTC) | `string` | `"sun:04:00-sun:05:00"` |
| `multi_az` | Enable Multi-AZ deployment | `bool` | `false` |
| `deletion_protection` | Enable deletion protection | `bool` | `false` |
| `skip_final_snapshot` | Skip final snapshot on deletion | `bool` | `false` |
| `enabled_cloudwatch_logs_exports` | Log types to export | `list(string)` | `["postgresql"]` |
| `performance_insights_enabled` | Enable Performance Insights | `bool` | `false` |
| `monitoring_interval` | Enhanced monitoring interval (seconds) | `number` | `0` |
| `tags` | Tags to apply to resources | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| `db_instance_id` | RDS instance ID |
| `db_instance_arn` | RDS instance ARN |
| `db_instance_endpoint` | RDS instance endpoint (hostname:port) |
| `db_instance_address` | RDS instance address (hostname only) |
| `db_instance_port` | RDS instance port |
| `db_instance_name` | Database name |
| `db_instance_username` | Master username (sensitive) |
| `db_instance_password` | Master password (legacy mode only; null when managed secret is enabled) |
| `master_user_secret_arn` | Secrets Manager ARN for the RDS managed master user secret |
| `db_subnet_group_id` | DB subnet group ID |
| `db_parameter_group_id` | DB parameter group ID |
| `db_instance_status` | RDS instance status |

## Security Considerations

- Storage is encrypted at rest by default (AES-256)
- Database is placed in private subnets only
- Access controlled via security groups (no public accessibility)
- Master password can be auto-generated and stored securely
- Enable `deletion_protection` in production
- Consider enabling Performance Insights for query analysis

## Cost Implications

| Resource | Dev (db.t3.medium) | Prod (db.m5.large) |
|----------|-------------------|-------------------|
| Instance | ~$50/month | ~$140/month |
| Storage (100GB gp3) | ~$10/month | ~$10/month |
| Multi-AZ | N/A | +$140/month |
| Backups (7 days) | ~$2/month | ~$5/month |

**Cost Optimization Tips:**
- Use `db.t3.*` instances for dev/test workloads
- Disable Multi-AZ in development
- Use gp3 storage (cheaper than gp2 for most workloads)
- Set appropriate `max_allocated_storage` to avoid over-provisioning

## Dependencies

- `network/vpc` - VPC and private subnets
- `security/security-group/rds` - RDS security group

## Dependent Modules

- `application/collibra-dq-standalone` - Connects to this database

## Password Management

Default behavior uses `manage_master_user_password = true`, so RDS stores and serves credentials from AWS Secrets Manager.

Legacy mode (not recommended) is still available by setting:

- `manage_master_user_password = false`
- and optionally `master_password` / `create_random_password`
