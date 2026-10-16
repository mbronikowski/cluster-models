#!/usr/bin/env python3
"""Build the static website into _site/ (validates the data first).

    python build.py               # build into _site/
    python build.py --out DIR     # build somewhere else
    python -m http.server -d _site 8000   # then open http://localhost:8000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cmdb import ROOT
from cmdb.checks import validate
from cmdb.data import load_database
from cmdb.site import Site, load_config


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "_site"), help="output directory (default: _site)")
    args = ap.parse_args(argv)

    db = load_database()
    report = validate(db)
    if report.errors:
        for where, msg in report.errors:
            print(f"ERROR   {where}: {msg}", file=sys.stderr)
        print(f"\n{len(report.errors)} error(s); run validate.py for details. Nothing built.",
              file=sys.stderr)
        return 1
    site = Site(db, Path(args.out), load_config())
    site.build()
    n = sum(1 for _ in Path(args.out).rglob("*.html"))
    print(f"Built {n} pages into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
