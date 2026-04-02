# S3 Package Storage Module
# Automatically uploads a local package file to S3 for use by EC2 instances

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# S3 bucket for storing packages (create if it doesn't exist)
resource "aws_s3_bucket" "package_storage" {
  count  = var.create_bucket ? 1 : 0
  bucket = var.bucket_name
  force_destroy = var.force_destroy

  tags = merge(var.tags, {
    Name      = var.bucket_name
    Component = "package-storage"
  })
}

# Use existing bucket if provided, otherwise use the created one
locals {
  bucket_id = var.create_bucket ? aws_s3_bucket.package_storage[0].id : var.bucket_name
}

# Bucket versioning
resource "aws_s3_bucket_versioning" "package_storage" {
  count  = var.create_bucket ? 1 : 0
  bucket = local.bucket_id

  versioning_configuration {
    status = "Enabled"
  }
}

# Bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "package_storage" {
  count  = var.create_bucket ? 1 : 0
  bucket = local.bucket_id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "package_storage" {
  count  = var.create_bucket ? 1 : 0
  bucket = local.bucket_id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable S3 Transfer Acceleration for faster uploads (optional)
resource "aws_s3_bucket_accelerate_configuration" "package_storage" {
  count  = var.create_bucket && var.enable_transfer_acceleration ? 1 : 0
  bucket = local.bucket_id

  status = "Enabled"
}

# Local values for package upload
locals {
  normalized_local_file_path = trimspace(var.local_file_path)
  should_upload_package      = local.normalized_local_file_path != "" ? fileexists(local.normalized_local_file_path) : false
  file_etag                  = local.should_upload_package ? filemd5(local.normalized_local_file_path) : null
  content_type_value = try(
    endswith(local.normalized_local_file_path, ".tar.gz") || endswith(local.normalized_local_file_path, ".tgz") ? "application/gzip" : (
      endswith(local.normalized_local_file_path, ".tar") ? "application/x-tar" : (
        endswith(local.normalized_local_file_path, ".zip") ? "application/zip" : "application/octet-stream"
      )
    ),
    "application/octet-stream"
  )
}

# Upload the package file to S3
# Best practice: Single resource with conditional lifecycle rules
# 
# When skip_upload_if_exists = false (default):
#   - File is uploaded/updated whenever local file changes (etag changes)
#   - Terraform automatically detects changes via etag comparison
#
# When skip_upload_if_exists = true:
#   - File is uploaded on first apply
#   - Subsequent changes to local file are ignored (lifecycle.ignore_changes)
#   - To force re-upload: set skip_upload_if_exists=false or use terraform taint
resource "aws_s3_object" "package" {
  count = local.should_upload_package ? 1 : 0

  bucket       = local.bucket_id
  key          = var.s3_key
  source       = local.normalized_local_file_path
  etag         = local.file_etag
  content_type = local.content_type_value

  # S3 object tags are limited to 10 key/value pairs. Bucket tags can be richer,
  # but object uploads must stay under this hard AWS limit.
  tags = {
    Name      = var.package_name
    Component = "package-storage"
  }

  # Lifecycle rules:
  # - Always ignore tags and content_type to prevent unnecessary updates
  # - Note: If you need to re-upload, either:
  #   1. Change the file locally (etag will change)
  #   2. Manually delete the S3 object and re-run terraform apply
  lifecycle {
    ignore_changes = [
      tags,
      content_type
    ]
  }

  depends_on = [
    aws_s3_bucket.package_storage,
    aws_s3_bucket_versioning.package_storage,
    aws_s3_bucket_server_side_encryption_configuration.package_storage,
    aws_s3_bucket_public_access_block.package_storage,
    aws_s3_bucket_accelerate_configuration.package_storage
  ]
}
