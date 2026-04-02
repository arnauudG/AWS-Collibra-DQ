terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

module "security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "5.1.0"

  name        = var.name
  description = var.description
  vpc_id      = var.vpc_id

  # Don't revoke rules on delete - RDS manages its own ENIs and we can't detach them manually
  # The RDS instance must be destroyed first before the security group can be deleted
  revoke_rules_on_delete = false

  # Ingress rules from security groups (e.g., EKS nodes)
  ingress_with_source_security_group_id = [
    for sg_id in var.allowed_security_group_ids : {
      from_port                = var.port
      to_port                  = var.port
      protocol                 = "tcp"
      description              = "Allow PostgreSQL access from security group ${sg_id}"
      source_security_group_id = sg_id
    }
  ]

  # Ingress rules from CIDR blocks
  ingress_with_cidr_blocks = [
    for cidr in var.allowed_cidr_blocks : {
      from_port   = var.port
      to_port      = var.port
      protocol     = "tcp"
      description  = "Allow PostgreSQL access from CIDR ${cidr}"
      cidr_blocks  = cidr
    }
  ]

  # Egress rules - allow all outbound (RDS doesn't need outbound, but module requires it)
  egress_rules = ["all-all"]

  tags = var.tags
}
