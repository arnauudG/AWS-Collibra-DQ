# ADR-M1: One generic S3 module for both shared and env-scoped storage

## Status

Accepted

## Context

The same S3 concerns apply to shared package buckets and env-scoped install-script buckets, even though lifecycle intent differs.

## Decision

Use one reusable S3 module with `create_bucket`, `local_file_path`, and `force_destroy` controls instead of separate modules.

## Rationale

- Reuses the same security and bucket management logic.
- Avoids duplicate Terraform for nearly identical resources.

## Consequences

- Callers must document intended lifecycle clearly.
- Module tests should validate both shared and env-scoped usage patterns.
