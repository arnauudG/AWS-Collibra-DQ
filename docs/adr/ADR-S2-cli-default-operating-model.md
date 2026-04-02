# ADR-S2: Orchestrated CLI is the default operating model

## Status

Accepted

## Context

Direct Terragrunt operations are useful for targeted debugging but do not carry the same retry, validation, and repair behaviors as the Python orchestrator.

## Decision

Document direct Terragrunt use as advanced-only and treat the CLI as the default operating model.

## Rationale

- The CLI includes recovery logic missing from raw Terragrunt.
- Reduces operator error during standard lifecycle operations.

## Consequences

- Day-to-day usage should stay CLI-driven.
- Direct Terragrunt flows need separate runbook coverage.
