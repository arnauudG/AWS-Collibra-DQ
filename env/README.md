# Terragrunt Configuration (`env/`)

This directory contains shared Terragrunt wiring and the live Collibra DQ stack definitions.

## Purpose

- centralize provider/backend generation (`common.hcl`)
- keep stack configuration environment-driven
- support reproducible deploy/destroy from the CLI orchestrator

## Structure

- `env/common.hcl`  
  Generates `provider.tf` and backend stubs for modules.
- `env/stack/README.md`  
  Stack-level map and execution notes.
- `env/stack/collibra-dq/root.hcl`  
  Main stack config: naming, tags, remote state, dynamic defaults.
- `env/stack/collibra-dq/**/terragrunt.hcl`  
  Module entry points for bootstrap, network, database, and addons.

## Configuration Model

This project intentionally avoids static env catalogs. Runtime values are injected by environment variables:

- Required core context: `TF_VAR_environment`, `TF_VAR_region`
- Reusable naming and client settings: `TG_*` variables
- Module-specific runtime options: `COLLIBRA_DQ_*` variables

All defaults and fallbacks are defined in `env/stack/collibra-dq/root.hcl`.

## How It Connects To The CLI

The CLI (`src/collibra_dq_starter/orchestrator.py`) executes terragrunt modules in deterministic order. Terragrunt config here defines:

- module source paths
- inter-module dependencies
- remote state location
- generated Terraform provider/backend files

Run from repo root:

```bash
# Artifact lifecycle (upload bucket/content only)
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target package

# Full stack lifecycle
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full
```
