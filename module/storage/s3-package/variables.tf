variable "bucket_name" {
  description = "Name of the S3 bucket for package storage (will be created if create_bucket is true)"
  type        = string
}

variable "create_bucket" {
  description = "Whether to create the S3 bucket (set to false if bucket already exists)"
  type        = bool
  default     = true
}

variable "force_destroy" {
  description = "When true, allow Terraform to delete a non-empty/versioned bucket by removing all objects and versions during destroy."
  type        = bool
  default     = false
}

variable "s3_key" {
  description = "S3 key (path) for the package file"
  type        = string
}

variable "local_file_path" {
  description = "Local file path to the package file (relative to terragrunt root or absolute)"
  type        = string
  default     = ""
}

variable "package_name" {
  description = "Name of the package (for tagging)"
  type        = string
  default     = "collibra-dq-package"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

variable "enable_transfer_acceleration" {
  description = "Enable S3 Transfer Acceleration for faster uploads (useful for large files). Note: This incurs additional AWS costs."
  type        = bool
  default     = false
}

variable "skip_upload_if_exists" {
  description = "Skip package upload if the file already exists in S3 (useful to avoid re-uploading large files). When true, the resource lifecycle ignores source/etag changes, preventing re-uploads. To force a re-upload, temporarily set this to false."
  type        = bool
  default     = false
}
