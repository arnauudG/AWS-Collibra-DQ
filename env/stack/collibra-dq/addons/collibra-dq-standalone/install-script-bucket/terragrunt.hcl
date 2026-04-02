# env/stack/collibra-dq/addons/collibra-dq-standalone/install-script-bucket/terragrunt.hcl
# Per-env S3 bucket for the rendered install script (contains env-specific secrets).
# Separate from the shared artifact bucket which holds the DQ package.

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

include "common" {
  path = find_in_parent_folders("common.hcl")
}

locals {
  org               = include.root.locals.org
  env               = include.root.locals.env
  aws_region        = include.root.locals.aws_region
  common_tags       = include.root.locals.common_tags
  actual_account_id = include.root.locals.actual_account_id

  bucket_name = "${local.actual_account_id}-${local.org}-${local.env}-collibra-dq-packages-${local.aws_region}"
}

terraform {
  source = "${include.root.locals.modules_root}/storage/s3-package"
}

inputs = {
  bucket_name     = local.bucket_name
  create_bucket   = true
  force_destroy   = true
  s3_key          = "collibra-dq/install_collibra_dq.sh"
  local_file_path = "" # no file upload, install script is managed by the EC2 module
  package_name    = "collibra-dq-install-script"

  tags = merge(local.common_tags, {
    Component = "install-script-storage"
  })
}
