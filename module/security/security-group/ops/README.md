# Generic Security Group Module (`ops`)

Reusable Terraform module that creates a security group and associated ingress/egress rules.

## Purpose

Use this module when you need a concise way to define:

- ingress rules from CIDR blocks
- ingress rules from other security groups
- egress rules to CIDR blocks

In this stack, it is used for:

- ALB security group (`sg-alb`)
- Collibra DQ EC2 security group (`sg-collibra-dq`)

## Usage

```hcl
module "sg" {
  source = "../../../module/security/security-group/ops"

  name        = "acme-dev-collibra-dq-sg"
  description = "Collibra DQ EC2 security group"
  vpc_id      = "vpc-123456"

  ingress_with_cidr_blocks = [
    {
      from_port   = 9000
      to_port     = 9000
      protocol    = "tcp"
      description = "DQ web traffic"
      cidr_blocks = "10.0.0.0/16"
    }
  ]

  ingress_with_source_security_group_id = [
    {
      from_port                = 9000
      to_port                  = 9000
      protocol                 = "tcp"
      description              = "From ALB"
      source_security_group_id = "sg-abcdef"
    }
  ]

  egress_with_cidr_blocks = [
    {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      description = "Allow all outbound"
      cidr_blocks = "0.0.0.0/0"
    }
  ]

  tags = {
    Env     = "dev"
    Project = "Collibra-DQ-Starter"
  }
}
```

## Inputs

### Required

- `name`
- `description`
- `vpc_id`

### Optional

- `ingress_with_cidr_blocks` (default: `[]`)
- `ingress_with_source_security_group_id` (default: `[]`)
- `egress_with_cidr_blocks` (default: `[]`)
- `tags` (default: `{}`)

## Outputs

- `security_group_id`
- `security_group_arn`

## Notes

- Rules are created with `aws_vpc_security_group_ingress_rule` / `aws_vpc_security_group_egress_rule`.
- Keep inbound rules minimal and explicit; avoid broad CIDR ranges in production.
- Prefer source security group references for service-to-service traffic within the VPC.
