# env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment/terragrunt.hcl
# Attach Collibra DQ instance to ALB target group

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

include "common" {
  path = find_in_parent_folders("common.hcl")
}

locals {
  org        = include.root.locals.org
  env        = include.root.locals.env
  aws_region = include.root.locals.aws_region
}

dependency "alb" {
  config_path  = ".."
  skip_outputs = false
  mock_outputs = {
    target_group_arns = {
      collibra-dq = "arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/mock-tg/1234567890123456"
    }
  }
  # Allow mocks for destroy in case of state drift (ALB might be destroyed before this)
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependency "collibra_dq" {
  config_path  = "../.."
  skip_outputs = false
  mock_outputs = {
    instance_id = "i-mock-123456"
  }
  # Allow mocks for destroy in case of state drift (EC2 might be destroyed before this)
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = [
    "..",
    "../.."
  ]
}

terraform {
  source = "${include.root.locals.modules_root}/network/alb/target-group-attachment"
}

inputs = {
  target_group_arn = dependency.alb.outputs.target_group_arns["collibra-dq"]
  target_id        = dependency.collibra_dq.outputs.instance_id
  port             = 9000
}
