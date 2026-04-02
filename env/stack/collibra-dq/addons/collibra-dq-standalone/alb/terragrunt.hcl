# env/stack/collibra-dq/addons/collibra-dq-standalone/alb/terragrunt.hcl
# Application Load Balancer for Collibra DQ Web Interface

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

include "common" {
  path = find_in_parent_folders("common.hcl")
}

locals {
  org         = include.root.locals.org
  org_prefix  = substr(local.org, 0, 2)
  env         = include.root.locals.env
  aws_region  = include.root.locals.aws_region
  common_tags = include.root.locals.common_tags
  alb_config  = include.root.locals.alb_config

  # HTTP-only listener (dev) - HTTPS/ACM can be added later with domain & certificate
  listeners_map = {
    http = {
      port     = 80
      protocol = "HTTP"
      forward = {
        target_group_key = "collibra-dq"
      }
    }
  }
}

dependency "vpc" {
  config_path  = "../../../network/vpc"
  skip_outputs = false
  mock_outputs = {
    vpc_id         = "vpc-123456"
    public_subnets = ["subnet-123456", "subnet-789012", "subnet-345678"]
  }
  # Allow mocks for destroy because VPC might be destroyed before ALB
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependency "sg_alb" {
  config_path  = "./sg-alb"
  skip_outputs = false
  mock_outputs = {
    security_group_id = "sg-mock-alb"
  }
  # Allow mocks for destroy because ALB SG might be destroyed before ALB
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = [
    "../../../network/vpc",
    "./sg-alb"
  ]
}

terraform {
  source = "${include.root.locals.modules_root}/network/alb/application"
}

inputs = {
  # Keep ALB/TG names short (max 32 chars) and VPC-suffixed to avoid collisions
  name    = "${local.org_prefix}-${local.env}-dq-${substr(replace(dependency.vpc.outputs.vpc_id, "vpc-", ""), length(replace(dependency.vpc.outputs.vpc_id, "vpc-", "")) - 6, 6)}-alb"
  vpc_id  = dependency.vpc.outputs.vpc_id
  subnets = dependency.vpc.outputs.public_subnets

  internal = false # Internet-facing ALB

  enable_deletion_protection       = local.alb_config.deletion_protection
  enable_http2                     = true
  enable_cross_zone_load_balancing = true

  security_groups = [dependency.sg_alb.outputs.security_group_id]

  enable_logging = local.env == "prod"

  listeners = local.listeners_map

  target_groups = {
    collibra-dq = {
      name                 = "${local.org_prefix}-${local.env}-dq-${substr(replace(dependency.vpc.outputs.vpc_id, "vpc-", ""), length(replace(dependency.vpc.outputs.vpc_id, "vpc-", "")) - 6, 6)}-tg"
      backend_protocol     = "HTTP"
      backend_port         = 9000
      target_type          = "instance"
      deregistration_delay = 30
      create_attachment    = false

      # Health checks:
      # - Use the traffic port (9000) so health does not depend on the agent binding on 9101.
      # - Accept 200-499 to tolerate redirects/auth responses during startup.
      health_check = {
        enabled             = true
        healthy_threshold   = 2
        interval            = 30
        matcher             = "200-499"
        path                = "/"
        port                = "traffic-port"
        protocol            = "HTTP"
        timeout             = 5
        unhealthy_threshold = 3
      }
    }
  }

  tags = merge(local.common_tags, {
    Component = "alb"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-alb"
  })
}
