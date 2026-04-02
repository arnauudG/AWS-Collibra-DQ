# ADR-C1: Standalone EC2 deployment model

## Status

Accepted

## Context

Collibra DQ is currently packaged and operated in a way that fits a standalone host model better than a container-orchestrated platform.

## Decision

Deploy Collibra DQ as a single standalone EC2 workload instead of introducing container orchestration.

## Rationale

- Matches the product packaging and bootstrap model.
- Keeps the platform operationally simple.
- Reduces moving parts for first deployment.

## Consequences

- Scaling and HA are limited compared to distributed/containerized models.
- Instance replacement and target re-registration remain important operational concerns.
