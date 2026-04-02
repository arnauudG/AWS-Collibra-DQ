# ADR-C3: HTTP-first ingress

## Status

Accepted

## Context

The baseline stack should be deployable without certificate ownership and ACM setup becoming blockers.

## Decision

Expose default ingress on HTTP only.

## Rationale

- Keeps baseline deployment simple.
- Removes certificate setup from the minimal working path.

## Consequences

- Operators must use `http://<alb-dns>/` by default.
- HTTPS must be added intentionally later.
