# ADR-003: Stack-scoped backend

## Status

Accepted

## Context

Terraform state is sensitive and operationally critical. Sharing backends across unrelated stacks increases blast radius and complicates teardown and recovery.

## Decision

Create dedicated backend resources per stack and environment in `bootstrap` using S3 and DynamoDB.

## Rationale

- Isolates failure domains.
- Makes full teardown possible without affecting other stacks.
- Aligns backend ownership with stack ownership.

## Consequences

- Bootstrap must exist before other modules run.
- Full destroy must treat backend deletion as a special case.
- Backend-destroy behavior must account for post-destroy state persistence errors.
