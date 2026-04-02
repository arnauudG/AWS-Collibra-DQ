---
tags: []

category: Documentation
type: data/readme
complexity: intermediate
time_required: 15-30 minutes
created: 2026-02-18
status: active
last_updated: 2026-02-18
---

# Security Group - RDS Module

Creates a security group specifically designed for RDS PostgreSQL instances.

## Description

This module creates an AWS Security Group configured for RDS database access. It allows:

- Ingress from specified security groups (e.g., application servers)
- Ingress from specified CIDR blocks
- Configurable PostgreSQL port (default 5432)

## Usage

```hcl
module "sg_rds" {
  source = "../../../module/security/security-group/rds"

  name        = "acme-dev-collibra-dq-rds-sg"
  description = "Security group for Collibra DQ RDS PostgreSQL"
  vpc_id      = dependency.vpc.outputs.vpc_id

  # Allow access from Collibra DQ instance
  allowed_security_group_ids = [
    dependency.sg_collibra_dq.outputs.security_group_id
  ]

  # Optional: Allow from specific CIDR
  allowed_cidr_blocks = []

  port = 5432

  tags = {
    Environment = "dev"
    Component   = "rds-sg"
  }
}
```

## Required Inputs

| Name | Description | Type |
|------|-------------|------|
| `name` | Name of the security group | `string` |
| `description` | Description of the security group | `string` |
| `vpc_id` | VPC ID where the security group will be created | `string` |

## Optional Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `allowed_security_group_ids` | Security group IDs allowed to access RDS | `list(string)` | `[]` |
| `allowed_cidr_blocks` | CIDR blocks allowed to access RDS | `list(string)` | `[]` |
| `port` | PostgreSQL port | `number` | `5432` |
| `tags` | Tags to apply to the security group | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| `security_group_id` | Security group ID |
| `security_group_arn` | Security group ARN |

## Security Considerations

- Only allow access from known application security groups
- Avoid using CIDR blocks unless absolutely necessary
- Never expose RDS directly to the internet
- Use VPC CIDR as a fallback, not `0.0.0.0/0`

## Dependencies

- `network/vpc` - VPC ID for security group placement

## Dependent Modules

- `database/rds/postgresql` - Uses this security group
