"""Command line entry for the parking allocation tool."""

from __future__ import annotations

import argparse
import csv
import sys

from .core import DataError, allocate, load_requests, load_spaces, score


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parkalloc", description="Fair parking allocation")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("allocate", help="assign spaces to requests")
    run.add_argument("spaces", help="spaces CSV")
    run.add_argument("requests", help="requests CSV")
    run.add_argument("--seed", type=int, default=0, help="tie-break seed (default 0)")
    run.add_argument("--out", help="also write assignments to this CSV")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Return 0 when everyone got a space, 1 when a waitlist exists, 2 on bad input."""
    args = build_parser().parse_args(argv)
    try:
        spaces = load_spaces(args.spaces)
        requests = load_requests(args.requests)
    except FileNotFoundError as exc:
        print(f"File not found: {exc.filename}", file=sys.stderr)
        return 2
    except DataError as exc:
        print(f"Bad input: {exc}", file=sys.stderr)
        return 2
    assignments, waitlist = allocate(spaces, requests, args.seed)
    print(f"{'employee':<14}{'need':<11}{'score':>6}  space")
    for req, space in sorted(assignments, key=lambda p: p[1].space_id):
        print(f"{req.employee:<14}{req.need:<11}{score(req):>6.1f}  {space.space_id} ({space.type}, {space.zone})")
    for req in waitlist:
        print(f"{req.employee:<14}{req.need:<11}{score(req):>6.1f}  WAITLIST")
    print(f"{len(assignments)} assigned, {len(waitlist)} on waitlist, {len(spaces) - len(assignments)} space(s) left")
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["employee", "need", "score", "space_id"])
            for req, space in assignments:
                writer.writerow([req.employee, req.need, f"{score(req):.1f}", space.space_id])
            for req in waitlist:
                writer.writerow([req.employee, req.need, f"{score(req):.1f}", "WAITLIST"])
    return 1 if waitlist else 0


if __name__ == "__main__":
    sys.exit(main())
