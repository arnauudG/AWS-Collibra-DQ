# ADR-004: Shared artifact bucket plus per-environment install-script bucket

## Status

Accepted

## Context

The Collibra package artifact is environment-agnostic, while the rendered install script contains environment-specific values and secrets.

## Decision

Use two S3 bucket roles:

- one shared artifact bucket for reusable package payloads
- one per-environment install-script bucket for rendered bootstrap/install scripts

## Rationale

- Avoids re-uploading a large package for every environment.
- Keeps rendered secrets scoped to a single environment.
- Preserves separate lifecycle semantics for shared artifacts and env-specific bootstrap content.

## Consequences

- `COLLIBRA_DQ_PACKAGE_URL` is optional in normal flow.
- Package lifecycle and install-script lifecycle are intentionally separate.
- Destroy logic must handle versioned S3 cleanup for both bucket types.
