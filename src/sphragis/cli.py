"""Minimal CLI: inspect declared governance, or evaluate an operation."""

from __future__ import annotations

import argparse
import json
import sys

from .model import Operation
from .parser import GOVERNANCE_GROUPS, parse_governance
from .policy import evaluate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sphragis")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="show declared governance metadata")
    p_inspect.add_argument("file")

    p_eval = sub.add_parser("evaluate", help="evaluate an operation against a document")
    p_eval.add_argument("file")
    p_eval.add_argument("--op", required=True, choices=[o.value for o in Operation])
    p_eval.add_argument("--permissive", action="store_true",
                        help="treat unspecified as not-denied (default is strict)")
    p_eval.add_argument("--involves-pii", action="store_true",
                        help="the concrete request would touch personal data")

    args = parser.parse_args(argv)
    gov = parse_governance(args.file)

    if args.command == "inspect":
        grouped = {
            group: {k: gov.elements[k] for k in names if k in gov.elements}
            for group, names in GOVERNANCE_GROUPS.items()
        }
        print(json.dumps({g: v for g, v in grouped.items() if v},
                         indent=2, ensure_ascii=False))
        return 0

    decision = evaluate(
        gov,
        Operation(args.op),
        strict=not args.permissive,
        involves_pii=args.involves_pii,
    )
    print(json.dumps(decision.to_dict(), indent=2, ensure_ascii=False))
    return 0 if decision.verdict.value != "deny" else 1


if __name__ == "__main__":
    sys.exit(main())
