variable "name" {
  description = "Name of the EC2 instance"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "ami" {
  description = "AMI ID"
  type        = string
  default     = null
}

variable "vpc_security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
}

variable "subnet_id" {
  description = "Subnet ID"
  type        = string
}

variable "root_block_device" {
  description = "Root block device configuration"
  type = object({
    volume_size           = optional(number)
    volume_type           = optional(string)
    iops                  = optional(number)
    throughput            = optional(number)
    encrypted             = optional(bool)
    delete_on_termination = optional(bool)
    kms_key_id            = optional(string)
  })
  default = null
}

variable "create_iam_instance_profile" {
  description = "Create IAM instance profile"
  type        = bool
  default     = true
}

variable "iam_role_name" {
  description = "IAM role name for the instance"
  type        = string
}

variable "iam_role_use_name_prefix" {
  description = "Use name prefix for IAM role"
  type        = bool
  default     = true
}

variable "iam_role_policies" {
  description = "IAM role policies"
  type        = map(string)
  default     = {}
}

variable "iam_inline_policies" {
  description = "Inline IAM policies (JSON) to attach to the instance role"
  type        = map(string)
  default     = {}
}

variable "metadata_options" {
  description = "Instance metadata options"
  type = object({
    http_endpoint               = string
    http_tokens                 = string
    http_put_response_hop_limit = number
    instance_metadata_tags      = string
  })
  default = {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }
}

variable "placement_group" {
  description = "Placement group"
  type        = string
  default     = null
}

variable "tenancy" {
  description = "Instance tenancy"
  type        = string
  default     = "default"
}

variable "ebs_optimized" {
  description = "Enable EBS optimization"
  type        = bool
  default     = false
}

variable "associate_public_ip_address" {
  description = "Associate public IP address"
  type        = bool
  default     = false
}

variable "monitoring" {
  description = "Enable detailed monitoring"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Collibra DQ specific variables
variable "owl_base" {
  description = "Base directory for Collibra DQ installation (OWL_BASE / OWL_HOME), e.g. /opt/collibra-dq"
  type        = string
  default     = "/opt/collibra-dq"
}

variable "owl_metastore_user" {
  description = "PostgreSQL metastore username (METASTORE_USER / OWL_METASTORE_USER, case-sensitive)"
  type        = string
  sensitive   = true
}

variable "owl_metastore_pass" {
  description = "PostgreSQL metastore password (METASTORE_PASS / OWL_METASTORE_PASS, case-sensitive)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "owl_metastore_secret_arn" {
  description = "Optional Secrets Manager ARN for RDS master secret. When set, installer reads password from this secret at runtime."
  type        = string
  default     = ""
}

variable "postgresql_host" {
  description = "PostgreSQL host (RDS endpoint)"
  type        = string
}

variable "postgresql_port" {
  description = "PostgreSQL port"
  type        = number
  default     = 5432
}

variable "postgresql_database" {
  description = "PostgreSQL database name"
  type        = string
  default     = "dqMetastore"
}

variable "spark_package" {
  description = "Spark package filename (e.g., spark-3.5.6-bin-hadoop3.tgz)"
  type        = string
  default     = "spark-3.5.6-bin-hadoop3.tgz"
}

variable "dq_admin_user_password" {
  description = "Password for DQ Web admin user (case-sensitive). Bootstrap-safe values must use only letters, digits, and underscore, include upper/lower/digit/underscore, and must not contain 'admin'."
  type        = string
  sensitive   = true
  default     = ""
}

variable "dq_package_url" {
  description = "Signed link/URL to the full Collibra DQ package (s3:// or https://)"
  type        = string
  default     = ""
}

variable "dq_package_filename" {
  description = "Filename of the DQ package (e.g., dq-full-package.tar.gz)"
  type        = string
  default     = "dq-full-package.tar.gz"
}

variable "license_key" {
  description = "Collibra DQ license key (required for activation; expiration date is not required in this workflow)"
  type        = string
  sensitive   = true
}

variable "license_name" {
  description = "Collibra DQ license name (required for activation - provided by Collibra in license provision email)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "owl_metastore_pass_ssm_parameter" {
  description = "Optional SSM parameter name (SecureString) containing owl_metastore_pass. When set, the value is fetched at runtime on EC2."
  type        = string
  default     = ""
}

variable "dq_admin_user_password_ssm_parameter" {
  description = "Optional SSM parameter name (SecureString) containing dq_admin_user_password. When set, the value is fetched at runtime on EC2."
  type        = string
  default     = ""
}

variable "license_key_ssm_parameter" {
  description = "Optional SSM parameter name (SecureString) containing license_key. When set, the value is fetched at runtime on EC2."
  type        = string
  default     = ""
}

variable "license_name_ssm_parameter" {
  description = "Optional SSM parameter name (SecureString) containing license_name. When set, the value is fetched at runtime on EC2."
  type        = string
  default     = ""
}

# Install script in S3 (avoids EC2 user data 16KB limit)
variable "install_script_bucket_name" {
  description = "S3 bucket name where the full install script is uploaded (same as package bucket)"
  type        = string
}

variable "install_script_s3_key" {
  description = "S3 object key for the install script"
  type        = string
  default     = "collibra-dq/install_collibra_dq.sh"
}
