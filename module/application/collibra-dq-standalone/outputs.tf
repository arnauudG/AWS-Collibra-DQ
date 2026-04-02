output "instance_id" {
  description = "EC2 instance ID"
  value       = module.ec2.id
}

output "instance_arn" {
  description = "EC2 instance ARN"
  value       = module.ec2.arn
}

output "instance_public_ip" {
  description = "Public IP address of the instance"
  value       = module.ec2.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the instance"
  value       = module.ec2.private_ip
}

output "iam_role_name" {
  description = "IAM role name attached to the instance"
  value       = module.ec2.iam_role_name
}

output "iam_role_arn" {
  description = "IAM role ARN attached to the instance"
  value       = module.ec2.iam_role_arn
}

output "owl_base" {
  description = "Base directory for Collibra DQ installation"
  value       = var.owl_base
}

output "dq_web_url" {
  description = "URL to access DQ Web (port 9000). Note: If instance is in private subnet, access via ALB instead."
  value       = module.ec2.public_ip != null ? "http://${module.ec2.public_ip}:9000" : "Access via ALB (instance in private subnet)"
}
