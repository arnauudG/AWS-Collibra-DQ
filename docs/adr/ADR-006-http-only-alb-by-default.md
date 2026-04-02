# ADR-006: HTTP-only ALB by default

## Status

Accepted

## Context

HTTPS requires certificate lifecycle, ACM ownership, and domain decisions that are not always available during initial environment bring-up.

## Decision

Default the ALB to an HTTP listener only.

## Rationale

- Removes certificate dependencies from baseline deployment.
- Shortens time-to-first-working environment.
- Keeps the default stack simpler to operate.

## Consequences

- Operators must use `http://<alb-dns>/` unless HTTPS is explicitly added.
- Browser errors on `https://` are expected in the default configuration.
- Future HTTPS support should be additive rather than forced into the baseline path.
