variable "name" {
  description = "Name prefix for event resources"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "instance_id" {
  description = "EC2 instance ID to restart"
  type        = string
}

variable "instance_arn" {
  description = "EC2 instance ARN to scope SendCommand permission"
  type        = string
}

variable "secret_arn" {
  description = "Secrets Manager ARN watched for rotation events"
  type        = string
}

variable "enabled" {
  description = "Enable event-driven restart wiring"
  type        = bool
  default     = true
}

variable "enable_alarms" {
  description = "Enable CloudWatch alarms for rotation/restart failures"
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "Alarm action ARNs (for example SNS topic ARNs)"
  type        = list(string)
  default     = []
}

variable "ok_actions" {
  description = "OK action ARNs (for example SNS topic ARNs)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to created resources"
  type        = map(string)
  default     = {}
}
