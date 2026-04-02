# ADR-001: CLI-first orchestration

## Status

Accepted

## Context

Deploy and destroy span backend bootstrap, shared storage, network, database, compute, ALB, and post-deploy recovery logic. Raw Terragrunt stacks alone do not express all runtime safety checks and retries cleanly.

## Decision

Use a Python CLI (`collibra_dq_starter.cli`) as the primary control plane and let it call Terragrunt in explicit order.

## Rationale

- Centralizes retry behavior and environment validation.
- Keeps S3 purge fallback and bootstrap recovery in one place.
- Reduces operator dependence on implicit Terragrunt behavior.

## Consequences

- Operators should prefer `uv run --no-editable python -m collibra_dq_starter.cli ...`.
- Direct Terragrunt remains available for debugging and targeted repairs.
- Orchestrator logic becomes a critical test surface.
