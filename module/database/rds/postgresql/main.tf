terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
  }
}

# Generate random password if not provided
resource "random_password" "master_password" {
  count            = !var.manage_master_user_password && var.create_random_password && var.master_password == "" ? 1 : 0
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Generate random ID for snapshot name uniqueness.
# The suffix is stable for a given state to avoid timestamp-driven plan churn.
resource "random_id" "snapshot_suffix" {
  count       = var.final_snapshot_identifier == "" && !var.skip_final_snapshot ? 1 : 0
  byte_length = 4
}

locals {
  master_password = var.manage_master_user_password ? null : (
    var.master_password != "" ? var.master_password : random_password.master_password[0].result
  )
  final_snapshot_name = var.final_snapshot_identifier != "" ? var.final_snapshot_identifier : (
    var.skip_final_snapshot ? null : "${local.name_lower}-${local.vpc_suffix}-final-snapshot-${random_id.snapshot_suffix[0].hex}"
  )
  # Convert name to lowercase for AWS resources that require it (subnet groups, parameter groups)
  # DB instance identifier can have uppercase, but subnet/parameter groups cannot
  name_lower = lower(var.name)

  # Some RDS resources (subnet/parameter groups) have globally-unique names per region.
  # Include a short VPC suffix so pre-existing resources from another VPC don't collide.
  vpc_id_compact = replace(var.vpc_id, "vpc-", "")
  vpc_suffix     = substr(local.vpc_id_compact, max(0, length(local.vpc_id_compact) - 6), 6)
}

# DB Subnet Group
resource "aws_db_subnet_group" "this" {
  name       = "${local.name_lower}-${local.vpc_suffix}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.name}-subnet-group"
    }
  )
}

# DB Parameter Group
resource "aws_db_parameter_group" "this" {
  # Keep a managed custom group attached so create/update/destroy lifecycles
  # remain deterministic across environments.
  name   = "${local.name_lower}-${local.vpc_suffix}-parameter-group"
  family = "postgres15"

  tags = merge(
    var.tags,
    {
      Name = "${var.name}-parameter-group"
    }
  )
}

# DB Instance
resource "aws_db_instance" "this" {
  # Suffix the identifier to avoid colliding with legacy instances created in another VPC.
  # This keeps the module "incremental" without requiring environment-variable overrides.
  identifier = "${local.name_lower}-${local.vpc_suffix}"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = var.storage_type
  storage_encrypted     = var.storage_encrypted

  db_name                     = var.database_name
  username                    = var.master_username
  password                    = local.master_password
  manage_master_user_password = var.manage_master_user_password

  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name
  vpc_security_group_ids = var.security_group_ids

  backup_retention_period = var.backup_retention_period
  backup_window           = var.backup_window
  maintenance_window      = var.maintenance_window

  multi_az                  = var.multi_az
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : local.final_snapshot_name

  enabled_cloudwatch_logs_exports = var.enabled_cloudwatch_logs_exports

  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_retention_period = var.performance_insights_enabled ? var.performance_insights_retention_period : null

  monitoring_interval = var.monitoring_interval
  monitoring_role_arn = var.monitoring_interval > 0 ? aws_iam_role.rds_enhanced_monitoring[0].arn : null

  # Auto minor version upgrade
  auto_minor_version_upgrade = true

  # Public access disabled (private only)
  publicly_accessible = false

  tags = merge(
    var.tags,
    {
      Name = var.name
    }
  )
}

# IAM Role for Enhanced Monitoring (if enabled)
resource "aws_iam_role" "rds_enhanced_monitoring" {
  count = var.monitoring_interval > 0 ? 1 : 0
  name  = "${local.name_lower}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  count      = var.monitoring_interval > 0 ? 1 : 0
  role       = aws_iam_role.rds_enhanced_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
