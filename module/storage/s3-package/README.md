---
tags: []

category: Documentation
type: data/readme
complexity: intermediate
time_required: 15-30 minutes
created: 2026-02-18
status: active
last_updated: 2026-04-01
---

# S3 Package Storage Module

Creates an S3 bucket and uploads package files for EC2 instance consumption.

## Intent

This module exists to solve two adjacent but different storage problems:

- store large deployable artifacts that can be downloaded by EC2 workloads
- optionally manage the bucket lifecycle itself when the bucket is part of the stack

It is reused for both:

- shared artifact bucket patterns
- per-environment install-script bucket patterns

## Description

This module creates an S3 bucket configured for storing software packages (like Collibra DQ) and automatically uploads a local file to the bucket. Features:

- Automatic bucket creation with security best practices
- Server-side encryption (AES-256)
- Versioning enabled
- Public access blocked
- Optional transfer acceleration for large files
- Smart upload logic (skip if exists)

## Usage

```hcl
module "package_upload" {
  source = "../../../module/storage/s3-package"

  bucket_name     = "acme-dev-collibra-dq-packages"
  create_bucket   = true
  s3_key          = "collibra-dq/dq-full-package.tar.gz"
  local_file_path = "/path/to/dq-full-package.tar.gz"
  package_name    = "collibra-dq-package"

  skip_upload_if_exists = true  # Don't re-upload if already exists

  tags = {
    Environment = "dev"
    Project     = "Collibra-DQ"
  }
}
```

## Required Inputs

| Name | Description | Type |
|------|-------------|------|
| `bucket_name` | Name of the S3 bucket | `string` |
| `s3_key` | S3 key (path) for the package file | `string` |

## Optional Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `create_bucket` | Whether to create the S3 bucket | `bool` | `true` |
| `force_destroy` | Allow destroy to remove all objects/versions before deleting bucket | `bool` | `false` |
| `local_file_path` | Local file path to upload | `string` | `""` |
| `package_name` | Name of the package (for tagging) | `string` | `"collibra-dq-package"` |
| `enable_transfer_acceleration` | Enable S3 Transfer Acceleration | `bool` | `false` |
| `skip_upload_if_exists` | Skip upload if file already exists | `bool` | `false` |
| `tags` | Tags to apply to resources | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| `bucket_id` | S3 bucket ID |
| `bucket_arn` | S3 bucket ARN |
| `object_key` | S3 object key |
| `object_etag` | S3 object ETag |

## Security Considerations

- Bucket is encrypted at rest with AES-256
- Public access is blocked at bucket level
- Versioning is enabled for recovery
- EC2 instances access via IAM role policies

## Cost Implications

| Resource | Cost |
|----------|------|
| S3 Storage (Standard) | ~$0.023/GB/month |
| S3 PUT requests | ~$0.005 per 1,000 |
| Transfer Acceleration | ~$0.04-0.08/GB (if enabled) |

**Cost Optimization Tips:**
- Use `skip_upload_if_exists = true` to avoid redundant uploads
- Only enable transfer acceleration for very large files or slow connections
- Set lifecycle policies for old versions (done automatically via bucket versioning)

## Dependencies

- None (standalone module)

## Dependent Modules

- `application/collibra-dq-standalone` - Downloads package from this bucket

## Upload Workflow

1. Set `local_file_path` to your package location
2. Run `terragrunt apply` - file uploads to S3
3. Set `skip_upload_if_exists = true` for subsequent runs
4. To force re-upload: temporarily set `skip_upload_if_exists = false`

## Destroy Semantics

- If bucket versioning is enabled and `force_destroy = false`, Terraform destroy fails when any object versions/delete markers remain.
- If `force_destroy = true`, Terraform attempts recursive cleanup during destroy.
- If objects were added outside Terraform (manual uploads, automation races), cleanup may still require an explicit purge/retry path in orchestration.

Recommended:

- `dev`: `force_destroy = true` for smoother teardown.
- `prod`: `force_destroy = false` unless explicitly approved by change control.

## ADR

Detailed ADRs live in [docs/adr/README.md](../../docs/adr/README.md).

- [ADR-M1](../../docs/adr/ADR-M1-generic-s3-module.md): use one generic S3 module for both shared and env-scoped storage patterns.
- [ADR-M2](../../docs/adr/ADR-M2-versioning-enabled-by-default.md): keep versioning enabled by default and handle destroy semantics explicitly.

## IAM Policy for EC2 Access

EC2 instances need this IAM policy to download packages:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::BUCKET_NAME",
        "arn:aws:s3:::BUCKET_NAME/*"
      ]
    }
  ]
}
```
