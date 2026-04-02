# Contributing

This project is a reusable Collibra DQ starter for client delivery. Contributions should improve reliability, clarity, and repeatable deployment outcomes.

## Working Model

- Use short-lived feature branches from `main`.
- Keep pull requests focused to one concern (docs, module behavior, orchestration logic, etc.).
- Prefer small incremental changes over large multi-topic diffs.
- Treat docs and runbooks as product artifacts, not optional extras.

## Commit Convention

Commits follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

`<type>(optional-scope): <imperative description>`

Examples:

```text
feat(orchestrator): add package upload preflight check
fix(alb): align health check matcher with stack defaults
docs(readme): expand troubleshooting runbook
chore(ci): run pre-commit in pull request workflow
```

## Pull Request Expectations

Each PR should include:

- Why this change is needed (problem/risk/client impact)
- What changed (high-level only)
- How it was validated (commands and environment)
- Any follow-up work explicitly called out

## Local Validation

Run before opening a PR:

```bash
pre-commit install
pre-commit run --all-files
```

Core CLI checks:

```bash
uv sync
uv run --no-editable python -m collibra_dq_starter.cli --help
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target stack
```

Optional (recommended) lifecycle smoke test:

```bash
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 deploy --target full
uv run --no-editable python -m collibra_dq_starter.cli --env dev --region eu-west-1 destroy --target all
```

## Documentation Standards

When behavior changes, update docs in the same PR:

- `README.md` for operator onboarding and command usage
- `env/stack/README.md` and `env/stack/collibra-dq/README.md` for stack/module behavior
- module README files when inputs/outputs/defaults change

Docs should always include:

- exact command examples
- environment variable expectations
- known failure modes and fixes

## Security and Secrets

- Never commit credentials, license keys, or passwords.
- Use environment variables or secure secret stores.
- Assume Terraform state may contain sensitive values; protect state backend access.

## Release Readiness Checklist

Use this before merging release-critical changes:

- [ ] `pre-commit run --all-files` passes
- [ ] CLI help and target commands execute
- [ ] Deploy target coverage validated (`bootstrap`, `stack`, `full`)
- [ ] Destroy target coverage validated (`addon`, `stack`, `all`)
- [ ] No broken doc links
- [ ] No references to removed scripts or legacy workflows
- [ ] No secrets in repo content/history

## Getting Help

- Product and operator guide: [README.md](README.md)
- Stack map and lifecycle: [env/stack/README.md](env/stack/README.md)
- Collibra stack details: [env/stack/collibra-dq/README.md](env/stack/collibra-dq/README.md)
