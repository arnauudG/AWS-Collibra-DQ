# Collibra DQ Package Artifact

Place the Collibra DQ installer artifact in this directory so the `package-upload` module can push it to S3 during deploy.

## Expected File

Default artifact file name:

- `dq-2025.11-SPARK356-JDK17-package-full.tar`

Override with:

```bash
export COLLIBRA_DQ_PACKAGE_FILENAME="<your-file-name>"
```

## Source

Download from Collibra product resources:

- [Collibra Data Quality downloads](https://productresources.collibra.com/downloads/data-quality-observability-classic-2025-11/)

## Upload Behavior

During `deploy --target package` (or auto-upload during `deploy --target full`), the package uploads to the **shared artifact bucket**:

`s3://${ACCOUNT_ID}-${TG_ORG}-collibra-dq-artifacts-${TF_VAR_region}/collibra-dq/`

This bucket is env-independent — upload once and all environments (dev, prod) read from it. No need to set `COLLIBRA_DQ_PACKAGE_URL` manually; the default points to the shared bucket.

**Upgrade workflow:** drop a new `.tar` here, run `deploy --target package`, then redeploy EC2 instances.

## Controls

- `COLLIBRA_DQ_SKIP_PACKAGE_UPLOAD=true`  
  Skip upload when package already exists and has not changed.
- `COLLIBRA_DQ_ENABLE_S3_ACCELERATION=true`  
  Enable S3 transfer acceleration where supported.

## Practical Guidance

- Keep only needed artifact versions locally to reduce disk usage.
- Expect 10-15 minutes upload time for multi-GB packages.
- Ensure artifact filename matches what your environment variables reference.

## Related Docs

- Parent package guide: [packages/README.md](../README.md)
- Stack runbook: [env/stack/collibra-dq/README.md](../../env/stack/collibra-dq/README.md)
