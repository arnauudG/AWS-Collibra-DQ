# Application Load Balancer Module

Creates an AWS Application Load Balancer with configurable listeners and target groups.

## Description

This module creates an Application Load Balancer (ALB) using the terraform-aws-modules/alb/aws module. It supports:

- Internet-facing or internal load balancers
- HTTP and HTTPS listeners
- Multiple target groups
- Health checks
- Access logging (optional)
- Cross-zone load balancing

## Usage

```hcl
module "alb" {
  source = "../../../module/network/alb/application"

  name    = "acme-dev-collibra-dq-alb"
  vpc_id  = dependency.vpc.outputs.vpc_id
  subnets = dependency.vpc.outputs.public_subnets

  security_groups = [dependency.sg_alb.outputs.security_group_id]

  internal = false  # Internet-facing

  listeners = {
    http = {
      port     = 80
      protocol = "HTTP"
      forward = {
        target_group_key = "dq-web"
      }
    }
  }

  target_groups = {
    dq-web = {
      name             = "collibra-dq-web-tg"
      backend_protocol = "HTTP"
      backend_port     = 9000
      target_type      = "instance"
      health_check = {
        enabled             = true
        healthy_threshold   = 2
        interval            = 30
        matcher             = "200-299"
        path                = "/"
        port                = "traffic-port"
        protocol            = "HTTP"
        timeout             = 5
        unhealthy_threshold = 3
      }
    }
  }

  tags = {
    Environment = "dev"
    Component   = "alb"
  }
}
```

## Required Inputs

| Name | Description | Type |
|------|-------------|------|
| `name` | Name of the load balancer | `string` |
| `vpc_id` | VPC ID where the ALB will be created | `string` |
| `subnets` | List of subnet IDs for the ALB | `list(string)` |
| `security_groups` | List of security group IDs | `list(string)` |

## Optional Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `internal` | Whether ALB is internal (private) | `bool` | `false` |
| `enable_deletion_protection` | Enable deletion protection | `bool` | `false` |
| `enable_http2` | Enable HTTP/2 | `bool` | `true` |
| `enable_cross_zone_load_balancing` | Enable cross-zone LB | `bool` | `true` |
| `enable_logging` | Enable access logging | `bool` | `false` |
| `log_bucket_name` | S3 bucket for access logs | `string` | `""` |
| `listeners` | Map of listener configurations | `map(object)` | `{}` |
| `target_groups` | Map of target group configurations | `map(object)` | `{}` |
| `tags` | Tags to apply to resources | `map(string)` | `{}` |

## Outputs

| Name | Description |
|------|-------------|
| `arn` | ALB ARN |
| `dns_name` | ALB DNS name |
| `zone_id` | ALB hosted zone ID |
| `target_groups` | Map of target group outputs |

## HTTPS Configuration

For HTTPS listeners, provide a certificate ARN:

```hcl
listeners = {
  https = {
    port            = 443
    protocol        = "HTTPS"
    certificate_arn = "arn:aws:acm:eu-west-1:123456789:certificate/abc-123"
    ssl_policy      = "ELBSecurityPolicy-TLS-1-2-2017-01"
    forward = {
      target_group_key = "dq-web"
    }
  }
  http-redirect = {
    port     = 80
    protocol = "HTTP"
    redirect = {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
```

## Security Considerations

- Use HTTPS in production (HTTP for dev only)
- Enable deletion protection in production
- Configure security groups to restrict access
- Enable access logging for audit trails
- Consider WAF integration for additional security

## Cost Implications

| Resource | Cost |
|----------|------|
| ALB (hourly) | ~$16/month |
| LCU (data processing) | ~$5.84 per LCU/month |

## Dependencies

- `network/vpc` - VPC and public subnets
- Security group for ALB

## Dependent Modules

- `network/alb/target-group-attachment` - Registers targets with ALB
