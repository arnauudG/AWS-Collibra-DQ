output "db_instance_id" {
  description = "RDS instance ID"
  value       = aws_db_instance.this.id
}

output "db_instance_arn" {
  description = "RDS instance ARN"
  value       = aws_db_instance.this.arn
}

output "db_instance_endpoint" {
  description = "RDS instance endpoint (hostname)"
  value       = aws_db_instance.this.endpoint
}

output "db_instance_address" {
  description = "RDS instance address (hostname without port)"
  value       = aws_db_instance.this.address
}

output "db_instance_port" {
  description = "RDS instance port"
  value       = aws_db_instance.this.port
}

output "db_instance_name" {
  description = "Database name"
  value       = aws_db_instance.this.db_name
}

output "db_instance_username" {
  description = "Master username"
  value       = aws_db_instance.this.username
  sensitive   = true
}

output "db_instance_password" {
  description = "Master password when not managed by AWS Secrets Manager"
  value       = var.manage_master_user_password ? null : local.master_password
  sensitive   = true
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN for the RDS-managed master user secret"
  value       = try(aws_db_instance.this.master_user_secret[0].secret_arn, null)
}

output "db_subnet_group_id" {
  description = "DB subnet group ID"
  value       = aws_db_subnet_group.this.id
}

output "db_parameter_group_id" {
  description = "DB parameter group ID"
  value       = aws_db_parameter_group.this.id
}

output "db_instance_status" {
  description = "RDS instance status"
  value       = aws_db_instance.this.status
}
