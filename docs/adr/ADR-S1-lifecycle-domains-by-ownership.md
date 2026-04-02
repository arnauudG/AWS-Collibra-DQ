# ADR-S1: Lifecycle domains are separated by ownership

## Status

Accepted

## Context

Backend, shared artifacts, infra, and app addons do not share the same lifecycle or blast radius.

## Decision

Keep backend, shared artifacts, infrastructure, and addons in separate Terragrunt folders and lifecycle domains.

## Rationale

- Supports selective deploy and selective destroy.
- Limits blast radius during targeted repairs.
- Makes ownership clearer for operators.

## Consequences

- CLI ordering matters.
- Documentation must explain lifecycle domain boundaries.
