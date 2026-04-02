output "load_balancer_id" {
  description = "The ID of the load balancer"
  value       = module.alb.id
}

output "load_balancer_arn" {
  description = "The ARN of the load balancer"
  value       = module.alb.arn
}

output "load_balancer_dns_name" {
  description = "The DNS name of the load balancer"
  value       = module.alb.dns_name
}

output "load_balancer_zone_id" {
  description = "The canonical hosted zone ID of the load balancer"
  value       = module.alb.zone_id
}

output "target_group_arns" {
  description = "ARNs of the target groups (map keyed by target group key)"
  value       = { for k, v in module.alb.target_groups : k => v.arn }
}

output "target_group_arn_suffixes" {
  description = "ARN suffixes of the target groups (map keyed by target group key)"
  value       = { for k, v in module.alb.target_groups : k => v.arn_suffix }
}

output "listener_arns" {
  description = "ARNs of the listeners (map keyed by listener key)"
  value       = { for k, v in module.alb.listeners : k => v.arn }
}
