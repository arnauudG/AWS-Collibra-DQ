locals {
  stack_name = "collibra-dq"

  env        = get_env("TF_VAR_environment", "dev")
  aws_region = get_env("TF_VAR_region", "eu-west-1")
  org        = get_env("TG_ORG", "dq")

  modules_root = "${dirname(dirname(dirname(dirname(find_in_parent_folders("root.hcl")))))}/module"
  tg_download_dir = pathexpand(
    get_env("TG_DOWNLOAD_DIR", "~/.terragrunt-cache")
  )

  # Allow static validation in environments without AWS credentials.
  actual_account_id = try(get_aws_account_id(), trimspace(get_env("TG_ACCOUNT_ID", "unknown-account")))

  defaults = {
    project     = get_env("TG_PROJECT", "Collibra-DQ-Starter")
    cost_center = get_env("TG_COST_CENTER", "Engineering")
  }

  vpc_config = {
    collibra_dq_cidr = get_env("TG_COLLIBRA_DQ_VPC_CIDR", local.env == "prod" ? "10.21.0.0/16" : "10.11.0.0/16")
    cidr             = get_env("TG_COLLIBRA_DQ_VPC_CIDR", local.env == "prod" ? "10.21.0.0/16" : "10.11.0.0/16")
    # Keep at least 2 AZs for ALB + RDS subnet-group compatibility, capped at 3.
    az_count           = max(2, min(3, tonumber(get_env("TG_VPC_AZ_COUNT", local.env == "prod" ? "3" : "2"))))
    single_nat_gateway = lower(get_env("TG_SINGLE_NAT_GATEWAY", local.env == "prod" ? "false" : "true")) == "true"
    enable_flow_log    = lower(get_env("TG_ENABLE_FLOW_LOG", local.env == "prod" ? "true" : "false")) == "true"
  }

  rds_config = {
    instance_class        = get_env("TG_RDS_INSTANCE_CLASS", local.env == "prod" ? "db.t3.small" : "db.t3.medium")
    allocated_storage     = tonumber(get_env("TG_RDS_ALLOCATED_STORAGE", "100"))
    max_allocated_storage = tonumber(get_env("TG_RDS_MAX_ALLOCATED_STORAGE", local.env == "prod" ? "500" : "200"))
    deletion_protection   = lower(get_env("TG_RDS_DELETION_PROTECTION", local.env == "prod" ? "true" : "false")) == "true"
    multi_az              = lower(get_env("TG_RDS_MULTI_AZ", local.env == "prod" ? "true" : "false")) == "true"
    backup_retention      = tonumber(get_env("TG_RDS_BACKUP_RETENTION", local.env == "prod" ? "14" : "7"))
  }

  collibra_dq_config = {
    instance_type     = get_env("TG_COLLIBRA_DQ_INSTANCE_TYPE", local.env == "prod" ? "m5.xlarge" : "m5.large")
    volume_size       = tonumber(get_env("TG_COLLIBRA_DQ_VOLUME_SIZE", local.env == "prod" ? "200" : "100"))
    # Dev cost optimization: place EC2 in public subnet to avoid NAT Gateway + VPC endpoint costs (~$55/mo).
    # Prod always uses private subnet for defense-in-depth.
    use_public_subnet = local.env == "prod" ? false : lower(get_env("TG_COLLIBRA_DQ_PUBLIC_SUBNET", "true")) == "true"
  }

  alb_config = {
    deletion_protection = lower(get_env("TG_ALB_DELETION_PROTECTION", local.env == "prod" ? "true" : "false")) == "true"
  }

  # Shared artifact bucket (env-independent): holds DQ packages uploaded once, read by all envs.
  # Override filename via COLLIBRA_DQ_PACKAGE_FILENAME (e.g. "dq-2026.01-SPARK360-JDK17-package-full.tar")
  _dq_package_filename = get_env("COLLIBRA_DQ_PACKAGE_FILENAME", "dq-2025.11-SPARK356-JDK17-package-full.tar")
  package_config = {
    artifact_bucket_name = "${local.actual_account_id}-${local.org}-collibra-dq-artifacts-${local.aws_region}"
    dq_package_filename  = local._dq_package_filename
    dq_package_s3_key    = "collibra-dq/${local._dq_package_filename}"
  }

  state_bucket = "${local.actual_account_id}-${local.org}-${local.env}-${local.stack_name}-tfstate-${local.aws_region}"
  lock_table   = "${local.actual_account_id}-${local.org}-${local.env}-${local.stack_name}-tf-locks"

  common_tags = {
    Terraform  = "true"
    ManagedBy  = "Terragrunt"
    Org        = local.org
    Env        = local.env
    Region     = local.aws_region
    Project    = local.defaults.project
    CostCenter = local.defaults.cost_center
    AccountId  = local.actual_account_id
    Stack      = local.stack_name
  }
}

remote_state {
  backend = "s3"
  config = {
    bucket         = local.state_bucket
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    dynamodb_table = local.lock_table
    encrypt        = true
  }
}

download_dir             = local.tg_download_dir
retry_max_attempts       = 3
retry_sleep_interval_sec = 3

inputs = {
  org          = local.org
  env          = local.env
  aws_region   = local.aws_region
  common_tags  = local.common_tags
  modules_root = local.modules_root

  vpc_config         = local.vpc_config
  rds_config         = local.rds_config
  collibra_dq_config = local.collibra_dq_config
  alb_config         = local.alb_config
  package_config     = local.package_config
}
