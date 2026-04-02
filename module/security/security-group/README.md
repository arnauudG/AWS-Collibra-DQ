# Security Group Modules Overview

Security group modules used by the Collibra DQ stack.

## Module Structure

```text
security-group/
├── ops/      # Generic SG module for ALB and Collibra EC2
├── rds/      # PostgreSQL-focused SG module
└── README.md
```

## Which Module To Use

### `ops/`

Use for components that need explicit custom rule lists:

- ALB security group
- Collibra DQ EC2 security group
- any additional app-tier SG with mixed ingress sources

### `rds/`

Use for PostgreSQL database access control:

- opens port `5432`
- supports source SG and/or CIDR restrictions
- intended for Collibra DQ metastore connectivity

## Current Traffic Model

```text
Internet -> ALB SG (80/443)
ALB SG -> Collibra EC2 SG (9000)
Collibra EC2 SG -> RDS SG (5432)
```

This model keeps DB access private and tied to application security groups.

## Best Practices

- Prefer security-group references over broad CIDR blocks for internal flows.
- Keep ingress rules minimal and purpose-specific.
- Add clear rule descriptions for auditability and reviews.
- Avoid `0.0.0.0/0` except for public ALB listeners where explicitly required.

## Troubleshooting

### ALB target unhealthy

- verify ALB SG egress to Collibra SG on `9000`
- verify Collibra SG ingress from ALB SG on `9000`
- verify service is listening on EC2

### App cannot reach database

- verify RDS SG allows ingress `5432` from Collibra SG
- verify Collibra SG egress permits `5432`
- verify DNS/route tables within VPC

## Related Documentation

- [Ops SG module](ops/README.md)
- [RDS SG module](rds/README.md)
- [VPC Endpoints](../../network/vpc-endpoints/README.md)
