# ADR-C4: Health-driven acceptance

## Status

Accepted

## Context

Bootstrap can report non-zero exit state while the service is already usable.

## Decision

Accept the environment as operational based on ALB target health and local app readiness rather than cloud-init success alone.

## Rationale

- Aligns acceptance with actual service availability.
- Reduces false rollback and rebuild triggers.

## Consequences

- Runbooks and troubleshooting prioritize service health over bootstrap status files.
- Health probes and ALB checks are first-class verification signals.
