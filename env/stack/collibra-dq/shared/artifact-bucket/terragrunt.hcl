# env/stack/collibra-dq/shared/artifact-bucket/terragrunt.hcl
# Shared S3 bucket for Collibra DQ artifacts (env-independent).
# Packages are uploaded once and consumed by all environments.

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

include "common" {
  path = find_in_parent_folders("common.hcl")
}

locals {
  package_config = include.root.locals.package_config
  common_tags    = include.root.locals.common_tags
  env            = include.root.locals.env
}

terraform {
  source = "${include.root.locals.modules_root}/storage/s3-package"
}

inputs = {
  bucket_name     = local.package_config.artifact_bucket_name
  create_bucket   = true
  force_destroy   = local.env == "prod" ? false : true
  s3_key          = local.package_config.dq_package_s3_key
  local_file_path = get_env("COLLIBRA_DQ_PACKAGE_LOCAL_PATH", "")
  package_name    = "collibra-dq-package"

  enable_transfer_acceleration = get_env("COLLIBRA_DQ_ENABLE_S3_ACCELERATION", "false") == "true"
  skip_upload_if_exists        = get_env("COLLIBRA_DQ_SKIP_PACKAGE_UPLOAD", "false") == "true"

  tags = merge(local.common_tags, {
    Component = "artifact-storage"
    Shared    = "true"
  })
}
