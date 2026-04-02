terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  ssm_document_arn           = "arn:aws:ssm:${var.region}::document/AWS-RunShellScript"
  rotation_target_alarm_name = substr("${var.name}-rotation-target-failures", 0, 255)
  restart_command_alarm_name = substr("${var.name}-restart-command-failures", 0, 255)
}

resource "aws_iam_role" "eventbridge_ssm" {
  count = var.enabled ? 1 : 0
  name  = "${var.name}-eventbridge-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "eventbridge_ssm" {
  count = var.enabled ? 1 : 0
  name  = "${var.name}-eventbridge-ssm-policy"
  role  = aws_iam_role.eventbridge_ssm[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:SendCommand"
        ]
        Resource = [
          local.ssm_document_arn,
          var.instance_arn
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "secret_rotation" {
  count       = var.enabled ? 1 : 0
  name        = "${var.name}-secret-rotation"
  description = "Restart Collibra DQ when RDS master secret rotates"

  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventSource = ["secretsmanager.amazonaws.com"]
      eventName   = ["RotateSecret", "PutSecretValue", "UpdateSecretVersionStage"]
      requestParameters = {
        secretId = [var.secret_arn]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "restart_service" {
  count    = var.enabled ? 1 : 0
  rule     = aws_cloudwatch_event_rule.secret_rotation[0].name
  arn      = local.ssm_document_arn
  role_arn = aws_iam_role.eventbridge_ssm[0].arn

  run_command_targets {
    key    = "InstanceIds"
    values = [var.instance_id]
  }

  input = jsonencode({
    commands = [
      "set -euo pipefail",
      "systemctl restart collibra-dq",
      "systemctl is-active --quiet collibra-dq"
    ]
    executionTimeout = ["3600"]
  })

  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 3
  }
}

resource "aws_cloudwatch_event_rule" "restart_command_failed" {
  count       = var.enabled ? 1 : 0
  name        = "${var.name}-restart-command-failed"
  description = "Capture failed SSM RunCommand executions for Collibra rotation restarts"

  event_pattern = jsonencode({
    source      = ["aws.ssm"]
    detail-type = ["EC2 Command Status-change Notification"]
    detail = {
      document-name = ["AWS-RunShellScript"]
      instance-id   = [var.instance_id]
      status        = ["Failed", "TimedOut", "Cancelled"]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "rotation_target_failures" {
  count               = var.enabled && var.enable_alarms ? 1 : 0
  alarm_name          = local.rotation_target_alarm_name
  alarm_description   = "EventBridge failed invoking SSM target for Collibra secret rotation restarts."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "FailedInvocations"
  namespace           = "AWS/Events"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    RuleName = aws_cloudwatch_event_rule.secret_rotation[0].name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "restart_command_failures" {
  count               = var.enabled && var.enable_alarms ? 1 : 0
  alarm_name          = local.restart_command_alarm_name
  alarm_description   = "SSM restart command failed after an RDS secret rotation event."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "MatchedEvents"
  namespace           = "AWS/Events"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    RuleName = aws_cloudwatch_event_rule.restart_command_failed[0].name
  }

  tags = var.tags
}
