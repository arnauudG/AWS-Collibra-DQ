# ADR-S3: Full deploy owns attachment ordering

## Status

Accepted

## Context

Target-group attachment depends on both the ALB outputs and the EC2 instance outputs. Trying to reconcile attachment too early creates race conditions.

## Decision

Treat `alb/target-group-attachment` as an explicit lifecycle step in orchestrated deploy rather than relying solely on local hooks.

## Rationale

- Avoids race conditions between EC2 and ALB output availability.
- Makes full deploy ordering explicit and predictable.

## Consequences

- Orchestrator order is part of platform correctness.
- Standalone hook remains optional for targeted flows only.
