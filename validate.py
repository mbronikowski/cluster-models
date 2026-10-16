#!/usr/bin/env python3
"""Validate everything under data/. Exit status 1 if there are errors.

    python validate.py            # errors and warnings
    python validate.py --quiet    # errors only
"""

from __future__ import annotations

import argparse
import sys

from cmdb.checks import validate
from cmdb.data import load_database


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true", help="do not print warnings")
    args = ap.parse_args(argv)

    db = load_database()
    report = validate(db)
    gh = "GITHUB_ACTIONS" in __import__("os").environ
    for where, msg in report.errors:
        print(f"::error file={where.split(' ')[0]}::{msg}" if gh else f"ERROR   {where}: {msg}")
    if not args.quiet:
        for where, msg in report.warnings:
            print(f"::warning file={where.split(' ')[0]}::{msg}" if gh else f"warning {where}: {msg}")
    print(f"\n{len(db.clusters)} clusters, {len(db.transients)} transients, "
          f"{len(db.programs)} programs: {len(report.errors)} error(s), "
          f"{len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
