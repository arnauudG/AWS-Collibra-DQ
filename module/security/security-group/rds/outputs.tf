output "security_group_id" {
  description = "Security group ID"
  value       = module.security_group.security_group_id
}

output "security_group_arn" {
  description = "Security group ARN"
  value       = module.security_group.security_group_arn
}
