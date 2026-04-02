# ADR-C2: Shared package artifact, env-specific rendered script

## Status

Accepted

## Context

The package is reusable across environments, but the rendered install bootstrap script contains environment-specific runtime values and secrets.

## Decision

Store the package once in shared artifact storage, but keep the rendered install bootstrap script per environment.

## Rationale

- Reduces artifact duplication.
- Keeps sensitive rendered content scoped to the environment.

## Consequences

- Shared artifact lifecycle differs from env-specific install-script lifecycle.
- Install-script rendering and bucket availability become explicit dependencies.
