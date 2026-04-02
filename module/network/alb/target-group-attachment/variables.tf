variable "target_group_arn" {
  description = "ARN of the target group"
  type        = string
}

variable "target_id" {
  description = "ID of the target (EC2 instance ID)"
  type        = string
}

variable "port" {
  description = "Port on which targets receive traffic"
  type        = number
  default     = 9000
}
