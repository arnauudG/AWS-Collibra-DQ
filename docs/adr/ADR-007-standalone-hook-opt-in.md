# ADR-007: Direct standalone hook is opt-in

## Status

Accepted

## Context

Automatic target re-attachment is useful during direct standalone applies, but it can interfere with orchestrated full-stack deploy if ALB outputs are not ready yet.

## Decision

Keep the direct standalone `after_hook` disabled by default and require `COLLIBRA_DQ_ENABLE_STANDALONE_HOOK=true` to enable it.

## Rationale

- Full deploy already owns target-group attachment in module order.
- Avoids race conditions during orchestrated deployment.
- Preserves convenience for targeted direct applies when explicitly requested.

## Consequences

- Full deploy remains stable by default.
- Direct standalone operators still have an automation path when they opt in.
- Hook behavior must be regression-tested against Terragrunt parsing and shell invocation edge cases.
