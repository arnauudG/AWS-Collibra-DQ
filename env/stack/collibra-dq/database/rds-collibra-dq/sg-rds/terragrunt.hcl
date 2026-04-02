# env/stack/collibra-dq/database/rds-collibra-dq/sg-rds/terragrunt.hcl
# RDS Security Group for Collibra DQ

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
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate"]
}

dependency "sg_collibra_dq" {
  config_path  = "../../../addons/collibra-dq-standalone/sg-collibra-dq"
  skip_outputs = false
  mock_outputs = {
    security_group_id = "sg-mock-collibra-dq"
  }
  # Allow mocks for destroy because RDS SG must be destroyed before Collibra DQ SG
  # (RDS SG has ingress rules referencing Collibra DQ SG)
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = [
    "../../../network/vpc",
    "../../../addons/collibra-dq-standalone/sg-collibra-dq"
  ]
}

terraform {
  source = "${include.root.locals.modules_root}/security/security-group/rds"
}

inputs = {
  name        = "${local.org}-${local.env}-collibra-dq-rds-sg"
  description = "Security group for Collibra DQ RDS PostgreSQL - allows access from Collibra DQ standalone instance"
  vpc_id      = dependency.vpc.outputs.vpc_id

  # Allow access from the Collibra DQ standalone instance.
  allowed_security_group_ids = [
    dependency.sg_collibra_dq.outputs.security_group_id
  ]

  port = 5432

  tags = merge(local.common_tags, {
    Component = "database-sg"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-rds-sg"
  })
}
