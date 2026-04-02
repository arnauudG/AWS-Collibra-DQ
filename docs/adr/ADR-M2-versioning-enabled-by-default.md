# ADR-M2: Versioning enabled by default

## Status

Accepted

## Context

Package storage benefits from recovery and auditability, but versioned buckets complicate destroy behavior.

## Decision

Keep versioning enabled by default for package storage.

## Rationale

- Improves recovery and artifact traceability.
- Matches safer S3 defaults for managed artifacts.

## Consequences

- Destroy becomes more complex unless `force_destroy = true`.
- Orchestration must handle version cleanup and retry logic.
