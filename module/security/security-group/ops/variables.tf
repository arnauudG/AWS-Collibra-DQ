variable "name" {
  description = "Security group name"
  type        = string
}

variable "description" {
  description = "Security group description"
  type        = string
}

variable "vpc_id" {
  description = "VPC id where the security group is created"
  type        = string
}

variable "ingress_with_cidr_blocks" {
  description = "Ingress rules using CIDR blocks"
  type = list(object({
    from_port   = number
    to_port     = number
    protocol    = string
    description = optional(string, "")
    cidr_blocks = string
  }))
  default = []
}

variable "ingress_with_source_security_group_id" {
  description = "Ingress rules using source security group IDs"
  type = list(object({
    from_port                = number
    to_port                  = number
    protocol                 = string
    description              = optional(string, "")
    source_security_group_id = string
  }))
  default = []
}

variable "egress_with_cidr_blocks" {
  description = "Egress rules using CIDR blocks"
  type = list(object({
    from_port   = number
    to_port     = number
    protocol    = string
    description = optional(string, "")
    cidr_blocks = string
  }))
  default = []
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
