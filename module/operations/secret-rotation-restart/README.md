# Secret Rotation Restart Module

Creates EventBridge -> SSM wiring to restart Collibra DQ when the RDS managed secret rotates.

## Flow

1. Secrets Manager rotation emits a CloudTrail-backed event.
2. EventBridge rule matches events for the configured secret ARN.
3. EventBridge target invokes SSM `AWS-RunShellScript` on the Collibra EC2 instance.
4. Command restarts `collibra-dq`.
5. CloudWatch alarms raise signal if restart orchestration fails.

## Inputs

- `name`
- `region`
- `instance_id`
- `instance_arn`
- `secret_arn`
- `enabled` (default: `true`)
- `enable_alarms` (default: `true`)
- `alarm_actions` (default: `[]`)
- `ok_actions` (default: `[]`)
- `tags`

## Outputs

- `event_rule_name`
- `event_rule_arn`
- `target_id`
- `restart_command_failed_rule_name`
- `rotation_target_failures_alarm_name`
- `restart_command_failures_alarm_name`

## Notes

- This is complementary to runtime pre-start secret refresh logic on the instance.
- Event delivery is best-effort with retries configured at the target level.
- Alarm `rotation_target_failures` watches EventBridge `FailedInvocations` for the rotation rule.
- Alarm `restart_command_failures` watches matched events for failed SSM restart commands.
