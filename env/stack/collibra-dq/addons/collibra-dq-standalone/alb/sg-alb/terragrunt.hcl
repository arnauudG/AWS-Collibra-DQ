# env/stack/collibra-dq/addons/collibra-dq-standalone/alb/sg-alb/terragrunt.hcl
# Security Group for Collibra DQ ALB

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
  config_path  = "../../../../network/vpc"
  skip_outputs = false
  mock_outputs = {
    vpc_id         = "vpc-123456"
    vpc_cidr_block = "10.10.0.0/16"
  }
  # Allow mocks for destroy because VPC might be destroyed before ALB SG
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = ["../../../../network/vpc"]
}

terraform {
  source = "${include.root.locals.modules_root}/security/security-group/ops"
}

inputs = {
  name        = "${local.org}-${local.env}-collibra-dq-alb-sg"
  description = "Security group for Collibra DQ ALB - allows HTTPS (443) and HTTP (80) from internet"
  vpc_id      = dependency.vpc.outputs.vpc_id

  # Ingress rules - allow HTTPS and HTTP from internet
  ingress_with_cidr_blocks = [
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      description = "Allow HTTPS from internet"
      cidr_blocks = "0.0.0.0/0"
    },
    {
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      description = "Allow HTTP from internet (will redirect to HTTPS)"
      cidr_blocks = "0.0.0.0/0"
    }
  ]

  # Egress rules - allow traffic to Collibra DQ web (port 9000)
  egress_with_cidr_blocks = [
    {
      from_port   = 9000
      to_port     = 9000
      protocol    = "tcp"
      description = "Allow traffic to Collibra DQ Web (port 9000)"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    }
  ]

  tags = merge(local.common_tags, {
    Component = "alb-sg"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-alb-sg"
  })
}
