# Packages

This directory stores vendor installation artifacts used during deployment.

## Purpose

- keep large binaries out of source-controlled infrastructure code
- provide a consistent local location for deploy workflows
- support repeatable package upload to stack-managed S3

## Current Package Path

- `packages/collibra-dq/` for Collibra DQ installation artifacts

See stack-specific instructions in [packages/collibra-dq/README.md](collibra-dq/README.md).

## Workflow Summary

1. Place the vendor artifact in the expected local folder (`packages/collibra-dq/`).
2. Deploy full stack (`deploy --target full`) — the CLI auto-uploads to the **shared artifact bucket** if not already present.
3. Or upload explicitly: `deploy --target package`.
4. All environments read the package from the same shared artifact bucket.

The shared artifact bucket (`<account>-<org>-collibra-dq-artifacts-<region>`) is env-independent. Upload the package once and all envs (dev, prod) consume it.

## Important Notes

- Artifact files are intentionally git-ignored.
- First upload can take several minutes depending on network.
- Use `COLLIBRA_DQ_SKIP_PACKAGE_UPLOAD=true` to avoid re-upload when unchanged.
- Optionally set `COLLIBRA_DQ_ENABLE_S3_ACCELERATION=true` where Transfer Acceleration is desired.

## Reference

- Product guide: [README.md](../README.md)
- Stack runbook: [env/stack/collibra-dq/README.md](../env/stack/collibra-dq/README.md)
