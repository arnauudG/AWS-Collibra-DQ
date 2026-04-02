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
  org         = include.root.locals.org
  env         = include.root.locals.env
  aws_region  = include.root.locals.aws_region
  common_tags = include.root.locals.common_tags
}

dependency "vpc" {
  config_path  = "../vpc"
  skip_outputs = false
  mock_outputs = {
    vpc_id                  = "vpc-123456"
    vpc_cidr_block          = "10.10.0.0/16"
    private_subnets         = ["subnet-a", "subnet-b", "subnet-c"]
    private_route_table_ids = ["rtb-a", "rtb-b", "rtb-c"]
  }
  # Allow mocks for destroy because VPC might be destroyed before VPC endpoints
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

  # Shared SG for Interface endpoints
  create_security_group      = true
  security_group_name        = "${local.org}-${local.env}-collibra-dq-vpce-sg"
  security_group_description = "Allow HTTPS from VPC to VPC Endpoints (Collibra DQ stack)"
  security_group_rules = [
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
  ]

  security_group_tags = merge(local.common_tags, {
    Component = "network"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-vpce-sg"
  })

  # Interface endpoints
  endpoints = {
    # SSM trio (Session Manager)
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

    # S3 Gateway endpoint (for package downloads)
    s3 = {
      service         = "s3"
      service_type    = "Gateway"
      route_table_ids = dependency.vpc.outputs.private_route_table_ids
      tags = merge(local.common_tags, {
        Component = "network"
        Stack     = "collibra-dq"
        Name      = "${local.org}-${local.env}-collibra-dq-vpce-s3"
      })
    }
  }

  tags = merge(local.common_tags, {
    Component = "network"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-vpce"
  })
}
