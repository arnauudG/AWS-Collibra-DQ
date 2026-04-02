# ADR-005: Cost-optimized dev defaults

## Status

Accepted

## Context

The immediate usage pattern is development and validation, not production-grade HA across all environments.

## Decision

Default development environments to a reduced-cost topology:

- one VPC
- minimum valid subnet footprint
- single NAT gateway
- single-AZ RDS

## Rationale

- Keeps iteration cost acceptable.
- Preserves the minimum topology required by ALB and RDS.
- Encourages faster rebuild cycles in dev.

## Consequences

- Dev is not equivalent to prod HA posture.
- Documentation must call out where prod should diverge.
- Test strategy should include env-default validation for `dev` vs `prod`.
