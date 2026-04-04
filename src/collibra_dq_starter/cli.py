from __future__ import annotations

import argparse
import os
import sys

from .orchestrator import destroy, deploy
from .shell import CommandError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dqctl",
        description="Collibra DQ deploy/destroy CLI.",
    )
    parser.add_argument(
        "--env",
        dest="environment",
        help="Sets TF_VAR_environment for this command.",
    )
    parser.add_argument(
        "--region",
        dest="region",
        help="Sets TF_VAR_region for this command.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subparsers.add_parser("deploy", help="Deploy resources.")
    deploy_parser.add_argument(
        "--target",
        choices=["bootstrap", "stack", "addon", "package", "full"],
        default="full",
        help="bootstrap=backend only, stack=backend+infra, addon=backend+addons, package=backend+artifact only, full=backend+infra+addons",
    )
    deploy_parser.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help="Run independent modules within each stage in parallel.",
    )

    destroy_parser = subparsers.add_parser("destroy", help="Destroy resources.")
    destroy_parser.add_argument(
        "--target",
        choices=["addon", "stack", "package", "all"],
        default="stack",
        help="addon=addons only, stack=addons+infra, package=artifact only, all=addons+infra+artifact+bootstrap",
    )
    destroy_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmations (use with caution).",
    )
    destroy_parser.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help="Run independent modules within each stage in parallel.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.environment:
        os.environ["TF_VAR_environment"] = args.environment
    if args.region:
        os.environ["TF_VAR_region"] = args.region

    try:
        if args.command == "deploy":
            deploy(args.target, parallel=getattr(args, "parallel", False))
        elif args.command == "destroy":
            destroy(
                args.target,
                auto_approve=getattr(args, "yes", False),
                parallel=getattr(args, "parallel", False),
            )
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except (RuntimeError, CommandError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[ERROR] Interrupted by user.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
