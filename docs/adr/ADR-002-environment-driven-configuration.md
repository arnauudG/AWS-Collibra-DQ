# ADR-002: Environment-driven configuration over per-client files

## Status

Accepted

## Context

This package is intended to be reused across accounts, environments, and customers without maintaining divergent repo branches or customer-specific stacks.

## Decision

Use environment variables (`TF_VAR_*`, `TG_*`, `COLLIBRA_*`) as the primary configuration interface.

## Rationale

- Keeps repository structure stable.
- Works cleanly with CI/CD secret stores and ephemeral environments.
- Makes reusable Terragrunt stack definitions practical.

## Consequences

- Documentation must clearly separate required, optional, and override variables.
- Runtime behavior depends on environment hygiene and explicit operator input.
- Validation logic in the CLI is part of platform safety.
