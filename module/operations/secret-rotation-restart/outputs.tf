output "event_rule_name" {
  description = "EventBridge rule name"
  value       = var.enabled ? aws_cloudwatch_event_rule.secret_rotation[0].name : null
}

output "event_rule_arn" {
  description = "EventBridge rule ARN"
  value       = var.enabled ? aws_cloudwatch_event_rule.secret_rotation[0].arn : null
}

output "target_id" {
  description = "EventBridge target ID"
  value       = var.enabled ? aws_cloudwatch_event_target.restart_service[0].target_id : null
}

output "restart_command_failed_rule_name" {
  description = "EventBridge rule name that captures failed restart commands"
  value       = var.enabled ? aws_cloudwatch_event_rule.restart_command_failed[0].name : null
}

output "rotation_target_failures_alarm_name" {
  description = "CloudWatch alarm name for EventBridge target invocation failures"
  value       = var.enabled && var.enable_alarms ? aws_cloudwatch_metric_alarm.rotation_target_failures[0].alarm_name : null
}

output "restart_command_failures_alarm_name" {
  description = "CloudWatch alarm name for failed restart commands"
  value       = var.enabled && var.enable_alarms ? aws_cloudwatch_metric_alarm.restart_command_failures[0].alarm_name : null
}
