# ADR-008: Service health over bootstrap status

## Status

Accepted

## Context

Cloud-init/bootstrap can report `PHASE=HANDOFF` and non-zero exit codes even when the application is already serving traffic and ALB health is good.

## Decision

Treat runtime service signals as the source of truth:

- ALB target healthy
- process listening on `:9000`
- local HTTP probe returns `200` or `302`

## Rationale

- Matches actual platform usability better than cloud-init exit state alone.
- Reduces false-negative incident response and unnecessary rebuilds.

## Consequences

- Runbooks explicitly distinguish blocking vs non-blocking bootstrap warnings.
- Operators should not rebuild solely because `status.env` is non-zero if service health is confirmed.
- Integration tests should validate this acceptance rule explicitly.
