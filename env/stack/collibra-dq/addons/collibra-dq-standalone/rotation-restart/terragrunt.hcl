# env/stack/collibra-dq/addons/collibra-dq-standalone/rotation-restart/terragrunt.hcl
# Event-driven restart when RDS secret rotates

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

include "common" {
  path = find_in_parent_folders("common.hcl")
}

locals {
  org                        = include.root.locals.org
  env                        = include.root.locals.env
  aws_region                 = include.root.locals.aws_region
  common_tags                = include.root.locals.common_tags
  rotation_alarm_actions_raw = trimspace(get_env("COLLIBRA_DQ_ROTATION_ALARM_ACTIONS", ""))
  rotation_ok_actions_raw    = trimspace(get_env("COLLIBRA_DQ_ROTATION_OK_ACTIONS", ""))
  rotation_alarm_actions = local.rotation_alarm_actions_raw == "" ? [] : [
    for action in split(",", local.rotation_alarm_actions_raw) : trimspace(action) if trimspace(action) != ""
  ]
  rotation_ok_actions = local.rotation_ok_actions_raw == "" ? [] : [
    for action in split(",", local.rotation_ok_actions_raw) : trimspace(action) if trimspace(action) != ""
  ]
}

dependency "collibra_dq_instance" {
  config_path  = ".."
  skip_outputs = false
  mock_outputs = {
    instance_id  = "i-0123456789abcdef0"
    instance_arn = "arn:aws:ec2:eu-west-1:123456789012:instance/i-0123456789abcdef0"
  }
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependency "rds" {
  config_path  = "../../../database/rds-collibra-dq/rds"
  skip_outputs = false
  mock_outputs = {
    master_user_secret_arn = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:mock-collibra-rds"
  }
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = [
    "..",
    "../../../database/rds-collibra-dq/rds"
  ]
}

terraform {
  source = "${include.root.locals.modules_root}/operations/secret-rotation-restart"
}

inputs = {
  name          = "${local.org}-${local.env}-collibra-dq-rotation"
  region        = local.aws_region
  instance_id   = dependency.collibra_dq_instance.outputs.instance_id
  instance_arn  = dependency.collibra_dq_instance.outputs.instance_arn
  secret_arn    = dependency.rds.outputs.master_user_secret_arn
  enabled       = lower(get_env("COLLIBRA_DQ_ENABLE_ROTATION_RESTART", "true")) == "true"
  enable_alarms = lower(get_env("COLLIBRA_DQ_ENABLE_ROTATION_ALARMS", "true")) == "true"
  alarm_actions = local.rotation_alarm_actions
  ok_actions    = local.rotation_ok_actions

  tags = merge(local.common_tags, {
    Component = "collibra-dq-rotation-restart"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-rotation-restart"
  })
}
