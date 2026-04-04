# env/stack/collibra-dq/network/vpc-endpoints/terragrunt.hcl
# VPC Endpoints configuration for Collibra DQ stack

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

include "common" {
  path = find_in_parent_folders("common.hcl")
}

locals {
  org                = include.root.locals.org
  env                = include.root.locals.env
  aws_region         = include.root.locals.aws_region
  common_tags        = include.root.locals.common_tags
  collibra_dq_config = include.root.locals.collibra_dq_config

  # Interface endpoints (SSM trio) are only needed when EC2 is in a private subnet.
  # In public subnet mode, SSM agent reaches AWS APIs over the internet — saves ~$22/mo.
  needs_interface_endpoints = !local.collibra_dq_config.use_public_subnet
}

dependency "vpc" {
  config_path  = "../vpc"
  skip_outputs = false
  mock_outputs = {
    vpc_id                  = "vpc-123456"
    vpc_cidr_block          = "10.10.0.0/16"
    private_subnets         = ["subnet-a", "subnet-b"]
    private_route_table_ids = ["rtb-a"]
    public_route_table_ids  = ["rtb-pub-a"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = ["../vpc"]
}

terraform {
  source = "${include.root.locals.modules_root}/network/vpc-endpoints"
}

inputs = {
  vpc_id = dependency.vpc.outputs.vpc_id

  # SG for interface endpoints (only created when interface endpoints are deployed)
  create_security_group      = local.needs_interface_endpoints
  security_group_name        = "${local.org}-${local.env}-collibra-dq-vpce-sg"
  security_group_description = "Allow HTTPS from VPC to VPC Endpoints (Collibra DQ stack)"
  security_group_rules = local.needs_interface_endpoints ? [
    {
      type        = "ingress"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      description = "Allow HTTPS from inside VPC"
      cidr_blocks = [dependency.vpc.outputs.vpc_cidr_block]
    },
    {
      type        = "egress"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      description = "Allow all egress"
      cidr_blocks = ["0.0.0.0/0"]
    }
  ] : []

  security_group_tags = merge(local.common_tags, {
    Component = "network"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-vpce-sg"
  })

  endpoints = merge(
    # Interface endpoints (SSM trio) — only for private subnet mode
    local.needs_interface_endpoints ? {
      ssm = {
        service             = "ssm"
        service_type        = "Interface"
        private_dns_enabled = true
        subnet_ids          = dependency.vpc.outputs.private_subnets
        tags = merge(local.common_tags, {
          Component = "network"
          Stack     = "collibra-dq"
          Name      = "${local.org}-${local.env}-collibra-dq-vpce-ssm"
        })
      }
      ssmmessages = {
        service             = "ssmmessages"
        service_type        = "Interface"
        private_dns_enabled = true
        subnet_ids          = dependency.vpc.outputs.private_subnets
        tags = merge(local.common_tags, {
          Component = "network"
          Stack     = "collibra-dq"
          Name      = "${local.org}-${local.env}-collibra-dq-vpce-ssmmessages"
        })
      }
      ec2messages = {
        service             = "ec2messages"
        service_type        = "Interface"
        private_dns_enabled = true
        subnet_ids          = dependency.vpc.outputs.private_subnets
        tags = merge(local.common_tags, {
          Component = "network"
          Stack     = "collibra-dq"
          Name      = "${local.org}-${local.env}-collibra-dq-vpce-ec2messages"
        })
      }
    } : {},
    # S3 Gateway endpoint (free, always included)
    # Attach to public + private route tables in public subnet mode
    {
      s3 = {
        service         = "s3"
        service_type    = "Gateway"
        route_table_ids = local.collibra_dq_config.use_public_subnet ? concat(
          dependency.vpc.outputs.public_route_table_ids,
          dependency.vpc.outputs.private_route_table_ids
        ) : dependency.vpc.outputs.private_route_table_ids
        tags = merge(local.common_tags, {
          Component = "network"
          Stack     = "collibra-dq"
          Name      = "${local.org}-${local.env}-collibra-dq-vpce-s3"
        })
      }
    }
  )

  tags = merge(local.common_tags, {
    Component = "network"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-vpce"
  })
}
