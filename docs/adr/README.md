# Architecture Decision Records

This directory contains the detailed Architecture Decision Records for the Collibra DQ AWS starter.

The README files in the repo keep short ADR summaries for fast scanning. This directory holds the full decision record for each topic.

## Core ADRs

- [ADR-001: CLI-first orchestration](ADR-001-cli-first-orchestration.md)
- [ADR-002: Environment-driven configuration over per-client files](ADR-002-environment-driven-configuration.md)
- [ADR-003: Stack-scoped backend](ADR-003-stack-scoped-backend.md)
- [ADR-004: Shared artifact bucket plus per-environment install-script bucket](ADR-004-shared-artifact-and-install-script-buckets.md)
- [ADR-005: Cost-optimized dev defaults](ADR-005-cost-optimized-dev-defaults.md)
- [ADR-006: HTTP-only ALB by default](ADR-006-http-only-alb-by-default.md)
- [ADR-007: Direct standalone hook is opt-in](ADR-007-standalone-hook-opt-in.md)
- [ADR-008: Service health over bootstrap status](ADR-008-service-health-over-bootstrap-status.md)

## Stack ADRs

- [ADR-S1: Lifecycle domains are separated by ownership](ADR-S1-lifecycle-domains-by-ownership.md)
- [ADR-S2: Orchestrated CLI is the default operating model](ADR-S2-cli-default-operating-model.md)
- [ADR-S3: Full deploy owns attachment ordering](ADR-S3-full-deploy-owns-attachment-ordering.md)

## Component ADRs

- [ADR-C1: Standalone EC2 deployment model](ADR-C1-standalone-ec2-deployment-model.md)
- [ADR-C2: Shared package artifact, env-specific rendered script](ADR-C2-shared-package-and-env-script.md)
- [ADR-C3: HTTP-first ingress](ADR-C3-http-first-ingress.md)
- [ADR-C4: Health-driven acceptance](ADR-C4-health-driven-acceptance.md)

## Module ADRs

- [ADR-M1: One generic S3 module for both shared and env-scoped storage](ADR-M1-generic-s3-module.md)
- [ADR-M2: Versioning enabled by default](ADR-M2-versioning-enabled-by-default.md)
