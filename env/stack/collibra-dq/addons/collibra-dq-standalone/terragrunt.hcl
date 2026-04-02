# env/stack/collibra-dq/addons/collibra-dq-standalone/terragrunt.hcl
# Collibra DQ Spark Standalone EC2 instance

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
  package_config     = include.root.locals.package_config
  account_id         = get_aws_account_id()

  # Collibra DQ configuration from environment variables
  owl_base               = get_env("COLLIBRA_DQ_OWL_BASE", "/opt/collibra-dq")
  spark_package          = get_env("COLLIBRA_DQ_SPARK_PACKAGE", "spark-3.5.6-bin-hadoop3.tgz")
  dq_admin_user_password = get_env("COLLIBRA_DQ_ADMIN_PASSWORD", "")
  dq_package_filename    = local.package_config.dq_package_filename
  license_key            = get_env("COLLIBRA_DQ_LICENSE_KEY", "")
  license_name           = get_env("COLLIBRA_DQ_LICENSE_NAME", "collibra-partners")
  ami_id_override        = trimspace(get_env("COLLIBRA_DQ_AMI_ID", ""))

  # Shared artifact bucket (env-independent, holds DQ package)
  artifact_bucket_name = local.package_config.artifact_bucket_name
  # Per-env bucket for install script (env-specific, contains rendered secrets)
  install_script_bucket_name = "${get_aws_account_id()}-${local.org}-${local.env}-collibra-dq-packages-${local.aws_region}"

  runtime_secret_parameters = compact([
    get_env("COLLIBRA_DQ_RDS_PASSWORD_SSM_PARAMETER", ""),
    get_env("COLLIBRA_DQ_ADMIN_PASSWORD_SSM_PARAMETER", ""),
    get_env("COLLIBRA_DQ_LICENSE_KEY_SSM_PARAMETER", ""),
    get_env("COLLIBRA_DQ_LICENSE_NAME_SSM_PARAMETER", "")
  ])
  runtime_secret_parameter_arns = [
    for param in local.runtime_secret_parameters :
    "arn:aws:ssm:${local.aws_region}:${local.account_id}:parameter${startswith(param, "/") ? param : "/${param}"}"
  ]
}

dependency "vpc" {
  config_path  = "../../network/vpc"
  skip_outputs = false
  mock_outputs = {
    vpc_id          = "vpc-123456"
    private_subnets = ["subnet-123456", "subnet-789012"]
    public_subnets  = ["subnet-345678", "subnet-901234"]
    vpc_cidr_block  = "10.10.0.0/16"
  }
  # Allow mocks for destroy because VPC might be destroyed before EC2 instance
  # Terragrunt will read real outputs during apply if skip_outputs = false
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependency "rds" {
  config_path  = "../../database/rds-collibra-dq/rds"
  skip_outputs = false
  mock_outputs = {
    db_instance_address    = "mock-rds-endpoint.rds.amazonaws.com"
    db_instance_port       = 5432
    db_instance_name       = "dqMetastore"
    db_instance_username   = "collibra_dq_admin"
    db_instance_password   = "mock-password"
    master_user_secret_arn = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:mock-collibra-rds"
  }
  # Allow mocks for destroy because RDS might be destroyed before EC2 instance
  # Terragrunt will read real outputs during apply if skip_outputs = false
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependency "sg_collibra_dq" {
  config_path  = "./sg-collibra-dq"
  skip_outputs = false
  mock_outputs = {
    security_group_id = "sg-mock-collibra-dq"
  }
  # Allow mocks for destroy because security group might be destroyed before EC2 instance
  # Terragrunt will read real outputs during apply if skip_outputs = false
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = [
    "../../network/vpc",
    "../../database/rds-collibra-dq/rds",
    "./sg-collibra-dq"
  ]
}

terraform {
  source = "${include.root.locals.modules_root}/application/collibra-dq-standalone"

  # Keep direct module applies seamless: when the standalone instance changes
  # (including replacement), auto-reconcile target registration.
  # In full-stack deploy, ALB may not exist yet at this stage, so skip gracefully.
  after_hook "reconcile_alb_target_attachment" {
    commands = ["apply"]
    execute = [
      "bash",
      "-c",
      <<-EOT
      set -eo pipefail

      # This hook is for direct standalone module applies only.
      # In orchestrated deploys, target-group-attachment is handled explicitly
      # later in the module order, so keep this disabled by default.
      if [ "$COLLIBRA_DQ_ENABLE_STANDALONE_HOOK" != "true" ]; then
        echo "[INFO] reconcile_alb_target_attachment: disabled (set COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true to enable)."
        exit 0
      fi

      cd "./alb/target-group-attachment"

      # Dependency ".." (ALB) might not be applied yet during full deploy.
      if ! terragrunt output --non-interactive --terragrunt-working-dir .. >/dev/null 2>&1; then
        echo "[INFO] reconcile_alb_target_attachment: ALB outputs not available yet; skipping."
        exit 0
      fi

      # Dependency "../.." (standalone module) must have outputs available.
      if ! terragrunt output --non-interactive --terragrunt-working-dir ../.. >/dev/null 2>&1; then
        echo "[INFO] reconcile_alb_target_attachment: standalone outputs not available yet; skipping."
        exit 0
      fi

      terragrunt apply --auto-approve --non-interactive
      EOT
    ]
    run_on_error = false
  }
}

inputs = {
  name   = "${local.org}-${local.env}-collibra-dq-standalone"
  region = local.aws_region

  # Instance configuration
  instance_type = local.collibra_dq_config.instance_type
  # Collibra DQ runtime requirement: CentOS/RHEL 7 compatible host.
  # Override directly via COLLIBRA_DQ_AMI_ID.
  ami = local.ami_id_override

  # Network configuration - private subnet, access via ALB
  subnet_id                   = dependency.vpc.outputs.private_subnets[0]
  associate_public_ip_address = false
  vpc_security_group_ids      = [dependency.sg_collibra_dq.outputs.security_group_id]

  # Storage configuration
  root_block_device = {
    volume_size           = local.collibra_dq_config.volume_size
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    encrypted             = true
    delete_on_termination = true
  }

  # IAM configuration
  create_iam_instance_profile = true
  iam_role_use_name_prefix    = false
  # Suffix the role name with the VPC id suffix to avoid colliding with legacy roles from previous stacks.
  iam_role_name = "${local.org}-${local.env}-collibra-dq-standalone-${substr(replace(dependency.vpc.outputs.vpc_id, "vpc-", ""), length(replace(dependency.vpc.outputs.vpc_id, "vpc-", "")) - 6, 6)}-role"

  iam_role_policies = {
    ssm = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  iam_inline_policies = {
    runtime_access = jsonencode({
      Version = "2012-10-17"
      Statement = concat(
        [
          {
            Effect = "Allow"
            Action = [
              "s3:GetObject"
            ]
            Resource = [
              "arn:aws:s3:::${local.artifact_bucket_name}/collibra-dq/*",
              "arn:aws:s3:::${local.install_script_bucket_name}/collibra-dq/*"
            ]
          },
          {
            Effect = "Allow"
            Action = [
              "s3:ListBucket"
            ]
            Resource = [
              "arn:aws:s3:::${local.artifact_bucket_name}",
              "arn:aws:s3:::${local.install_script_bucket_name}"
            ]
          },
          {
            Effect = "Allow"
            Action = [
              "logs:CreateLogGroup",
              "logs:CreateLogStream",
              "logs:PutLogEvents",
              "logs:DescribeLogStreams"
            ]
            Resource = [
              "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/ec2/${local.org}-${local.env}-collibra-dq-standalone*",
              "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/ec2/${local.org}-${local.env}-collibra-dq-standalone*:log-stream:*"
            ]
          },
          {
            Effect = "Allow"
            Action = [
              "secretsmanager:GetSecretValue"
            ]
            Resource = [
              dependency.rds.outputs.master_user_secret_arn
            ]
          }
        ],
        length(local.runtime_secret_parameter_arns) > 0 ? [
          {
            Effect = "Allow"
            Action = [
              "ssm:GetParameter"
            ]
            Resource = local.runtime_secret_parameter_arns
          }
        ] : []
      )
    })
  }

  # Metadata options
  metadata_options = {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  placement_group = null
  tenancy         = "default"
  ebs_optimized   = true
  monitoring      = true

  # Collibra DQ configuration
  owl_base                 = local.owl_base
  owl_metastore_user       = dependency.rds.outputs.db_instance_username
  owl_metastore_pass       = ""
  owl_metastore_secret_arn = dependency.rds.outputs.master_user_secret_arn
  postgresql_host          = dependency.rds.outputs.db_instance_address
  postgresql_port          = dependency.rds.outputs.db_instance_port
  postgresql_database      = dependency.rds.outputs.db_instance_name
  spark_package            = local.spark_package
  dq_admin_user_password   = local.dq_admin_user_password
  # Package URL: always reads from shared artifact bucket (env-independent).
  # To override, set COLLIBRA_DQ_PACKAGE_URL_OVERRIDE (not COLLIBRA_DQ_PACKAGE_URL, which is
  # used internally by the orchestrator and may contain stale values).
  dq_package_url      = length(trimspace(get_env("COLLIBRA_DQ_PACKAGE_URL_OVERRIDE", ""))) > 0 ? trimspace(get_env("COLLIBRA_DQ_PACKAGE_URL_OVERRIDE", "")) : "s3://${local.artifact_bucket_name}/${local.package_config.dq_package_s3_key}"
  dq_package_filename = local.dq_package_filename
  license_key         = local.license_key
  license_name        = local.license_name
  # Optional runtime secret resolution from SSM Parameter Store (SecureString).
  # When provided, module avoids embedding these values into rendered install script content/state.
  owl_metastore_pass_ssm_parameter     = get_env("COLLIBRA_DQ_RDS_PASSWORD_SSM_PARAMETER", "")
  dq_admin_user_password_ssm_parameter = get_env("COLLIBRA_DQ_ADMIN_PASSWORD_SSM_PARAMETER", "")
  license_key_ssm_parameter            = get_env("COLLIBRA_DQ_LICENSE_KEY_SSM_PARAMETER", "")
  license_name_ssm_parameter           = get_env("COLLIBRA_DQ_LICENSE_NAME_SSM_PARAMETER", "")

  # Install script in S3 (per-env bucket, contains rendered secrets)
  install_script_bucket_name = local.install_script_bucket_name
  install_script_s3_key      = "collibra-dq/install_collibra_dq.sh"

  tags = merge(local.common_tags, {
    Component = "collibra-dq-standalone"
    Stack     = "collibra-dq"
    Name      = "${local.org}-${local.env}-collibra-dq-standalone"
  })
}
