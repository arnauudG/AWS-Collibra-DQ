output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = local.bucket_id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = var.create_bucket ? aws_s3_bucket.package_storage[0].arn : "arn:aws:s3:::${var.bucket_name}"
}

output "s3_url" {
  description = "S3 URL for the package file"
  value       = "s3://${local.bucket_id}/${var.s3_key}"
}

output "package_uploaded" {
  description = "Whether the package was uploaded (true if local file exists and was uploaded)"
  value       = local.should_upload_package && length(aws_s3_object.package) > 0
}
