# env/stack/collibra-dq/addons/collibra-dq-standalone/package-upload/terragrunt.hcl
# Uploads Collibra DQ package to the shared artifact bucket.
# The shared bucket is env-independent: upload once, deploy everywhere.

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

include "common" {
  path = find_in_parent_folders("common.hcl")
}

locals {
  common_tags    = include.root.locals.common_tags
  package_config = include.root.locals.package_config

  dq_package_filename = local.package_config.dq_package_filename

  # Package file path (absolute path to ensure Terraform can find it from .terragrunt-cache)
  package_local_path = get_env(
    "COLLIBRA_DQ_PACKAGE_LOCAL_PATH",
    "${get_terragrunt_dir()}/../../../../../../packages/collibra-dq/${local.dq_package_filename}"
  )
}

dependency "artifact_bucket" {
  config_path  = "../../../shared/artifact-bucket"
  skip_outputs = false
  mock_outputs = {
    bucket_name = "mock-artifact-bucket"
  }
  mock_outputs_allowed_terraform_commands = ["init", "plan", "validate", "destroy"]
}

dependencies {
  paths = ["../../../shared/artifact-bucket"]
}

terraform {
  source = "${include.root.locals.modules_root}/storage/s3-package"
}

inputs = {
  bucket_name                  = dependency.artifact_bucket.outputs.bucket_name
  create_bucket                = false # bucket already created by shared/artifact-bucket
  s3_key                       = local.package_config.dq_package_s3_key
  local_file_path              = local.package_local_path
  package_name                 = "collibra-dq-package"
  enable_transfer_acceleration = get_env("COLLIBRA_DQ_ENABLE_S3_ACCELERATION", "false") == "true"
  skip_upload_if_exists        = get_env("COLLIBRA_DQ_SKIP_PACKAGE_UPLOAD", "false") == "true"

  tags = local.common_tags
}
