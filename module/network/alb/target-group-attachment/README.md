---
tags: []

category: Documentation
type: data/readme
complexity: intermediate
time_required: 15-30 minutes
created: 2026-02-18
status: active
last_updated: 2026-04-01
---

# Target Group Attachment Module

Registers EC2 instances with an ALB target group.

## Description

This module creates a target group attachment to register an EC2 instance (or other target) with an Application Load Balancer target group.

## Usage

```hcl
module "tg_attachment" {
  source = "../../../module/network/alb/target-group-attachment"

  target_group_arn = dependency.alb.outputs.target_groups["dq-web"].arn
  target_id        = dependency.collibra_dq.outputs.instance_id
  port             = 9000
}
```

## Required Inputs

| Name | Description | Type |
|------|-------------|------|
| `target_group_arn` | ARN of the target group | `string` |
| `target_id` | ID of the target (EC2 instance ID) | `string` |

## Optional Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `port` | Port on which targets receive traffic | `number` | `9000` |

## Outputs

| Name | Description |
|------|-------------|
| `id` | Target group attachment ID |

## Dependencies

- `network/alb/application` - ALB with target groups
- EC2 instance to register

## Related Modules

- `network/alb/application` - Creates the ALB and target groups

## Operational Guidance

This module must be reconciled whenever the standalone EC2 instance is replaced.
Direct apply on `addons/collibra-dq-standalone` now auto-runs this module via an
`after_hook`, so manual re-apply is a fallback path.

Typical trigger:

- `addons/collibra-dq-standalone` plan shows instance `-/+` replacement.

Fallback manual follow-up:

```bash
cd env/stack/collibra-dq/addons/collibra-dq-standalone/alb/target-group-attachment
terragrunt apply --auto-approve
```

Verification:

```bash
aws elbv2 describe-target-health \
  --region "<region>" \
  --target-group-arn "<target-group-arn>" \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Reason,TargetHealth.Description]' \
  --output table
```

Interpretation:

- Empty output means no target is attached (ALB likely returns `503`).
- `healthy` means traffic is routable to the instance.
