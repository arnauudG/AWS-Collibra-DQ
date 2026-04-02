# env/stack/collibra-dq/addons/collibra-dq-standalone/sg-collibra-dq/terragrunt.hcl
# Security Group for Collibra DQ Standalone instance

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
  config_path  = "../../../network/vpc"
  skip_outputs = false
  mock_outputs = {
    vpc_id         = "vpc-123456"
    vpc_cidr_block = "10.10.0.0/16"
  }
  # Allow mocks for destroy because VPC might be destroyed before security group
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependency "sg_alb" {
  config_path  = "../alb/sg-alb"
  skip_outputs = false
  mock_outputs = {
    security_group_id = "sg-mock-alb"
  }
  # Allow mocks for destroy because EC2 SG must be destroyed before ALB SG
  # (EC2 SG has ingress rules referencing ALB SG)
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = [
    "../../../network/vpc",
    "../alb/sg-alb" # Ensure ALB SG is created before Collibra DQ SG
  ]
}

terraform {
  source = "${include.root.locals.modules_root}/security/security-group/ops"
}

inputs = {
  name        = "${local.org}-${local.env}-collibra-dq-standalone-sg"
  description = "Security group for Collibra DQ Standalone instance - allows access to DQ Web (port 9000)"
  vpc_id      = dependency.vpc.outputs.vpc_id

  # Ingress rules - allow access from ALB only (more secure)
  ingress_with_source_security_group_id = [
    {
      from_port                = 9000
      to_port                  = 9000
      protocol                 = "tcp"
      description              = "Allow access to Collibra DQ Web interface from ALB"
      source_security_group_id = dependency.sg_alb.outputs.security_group_id
    }
  ]

  # Ingress rules - allow access to health check and Spark UIs from VPC (for monitoring)
  ingress_with_cidr_blocks = [
    {
      from_port   = 9101
      to_port     = 9101
      protocol    = "tcp"
      description = "Allow access to Collibra DQ Agent health check API from VPC"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    },
    {
      from_port   = 8080
      to_port     = 8080
      protocol    = "tcp"
      description = "Allow access to Spark Master Web UI from VPC"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    },
    {
      from_port   = 8081
      to_port     = 8081
      protocol    = "tcp"
      description = "Allow access to Spark Worker Web UI from VPC"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    },
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      description = "Allow SSM Session Manager access"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    }
  ]

  # Egress rules
  egress_with_cidr_blocks = [
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      description = "HTTPS to internet (for package downloads) and VPC endpoints"
      cidr_blocks = "0.0.0.0/0"
    },
    {
      from_port   = 53
      to_port     = 53
      protocol    = "udp"
      description = "DNS UDP to VPC resolver"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    },
    {
      from_port   = 53
      to_port     = 53
      protocol    = "tcp"
      description = "DNS TCP to VPC resolver"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    },
    {
      from_port   = 123
      to_port     = 123
      protocol    = "udp"
      description = "NTP to AWS Time Sync service"
      cidr_blocks = "169.254.169.123/32"
    },
    {
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      description = "HTTP for package updates to AWS repositories"
      cidr_blocks = "0.0.0.0/0"
    },
    {
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      description = "Allow outbound to RDS PostgreSQL"
      cidr_blocks = dependency.vpc.outputs.vpc_cidr_block
    }
  ]

  tags = merge(local.common_tags, {
    Component = "collibra-dq-standalone-sg"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-standalone-sg"
  })
}
