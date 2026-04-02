# Application Load Balancer Module
# Wraps terraform-aws-modules/alb/aws and provides standardized outputs

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

module "alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "9.0.0"

  name = var.name

  load_balancer_type = "application"
  internal           = var.internal
  vpc_id             = var.vpc_id
  subnets            = var.subnets

  enable_deletion_protection       = var.enable_deletion_protection
  enable_http2                     = var.enable_http2
  enable_cross_zone_load_balancing = var.enable_cross_zone_load_balancing

  # Security groups
  create_security_group = false
  security_groups       = var.security_groups

  # Access logs (v9.0.0 uses access_logs map instead of enable_logging)
  # Only set access_logs if logging is enabled and bucket is provided
  access_logs = var.enable_logging && var.log_bucket_name != "" ? {
    bucket = var.log_bucket_name
  } : {}

  # Listeners - transform to ensure only one action type is present
  # The module may check all action types, so we only include the one being used
  listeners = {
    for k, v in var.listeners : k => merge(
      {
        port            = v.port
        protocol        = v.protocol
        certificate_arn = v.certificate_arn
        ssl_policy      = v.ssl_policy
      },
      v.forward != null ? { forward = v.forward } : {},
      v.fixed_response != null ? { fixed_response = v.fixed_response } : {},
      v.redirect != null ? { redirect = v.redirect } : {}
    )
  }

  # Target groups (v9.0.0 - targets attached separately, not in target_groups)
  target_groups = var.target_groups

  tags = var.tags
}
