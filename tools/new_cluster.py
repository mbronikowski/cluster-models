#!/usr/bin/env python3
"""Create a new cluster file with the right name and layout.

    python tools/new_cluster.py "eMACS J0030.5+2618" 00:30:33.6 +26:18:15 0.497

Writes data/clusters/<slug>.yaml (the slug writes '+' as 'p' and a minus sign
as 'm') and checks that the designation is known to data/catalogues.yaml and
agrees with the position. Edit the file afterwards to add designations and models.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cmdb import yamlio  # noqa: E402
from cmdb.catalogues import identify, position_excess  # noqa: E402
from cmdb.coords import parse_dec, parse_ra  # noqa: E402
from cmdb.text import slugify, strict_ascii_problems  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name", help="primary designation, e.g. 'MACS J0416.1-2403'")
    ap.add_argument("ra", help="J2000 RA, hh:mm:ss.s")
    ap.add_argument("dec", help="J2000 Dec, +dd:mm:ss.s (sign required)")
    ap.add_argument("z", type=float, help="cluster redshift")
    args = ap.parse_args(argv)

    problems = strict_ascii_problems(args.name)
    if problems:
        sys.exit(f"name: {'; '.join(problems)}")
    ra, dec = parse_ra(args.ra), parse_dec(args.dec)
    hits = identify(args.name)
    if not hits:
        print(f"warning: {args.name!r} matches no catalogue in data/catalogues.yaml; "
              "validation will fail until it is added")
    else:
        excess = position_excess(hits[0], ra, dec)
        if excess is not None and excess > hits[0].pattern.tolerance:
            print(f"warning: the designation encodes a position {excess:.1f}' from ra/dec")
    path = ROOT / "data" / "clusters" / f"{slugify(args.name)}.yaml"
    if path.exists():
        sys.exit(f"{path.relative_to(ROOT)} already exists")
    rec = {"name": args.name, "ra": args.ra, "dec": args.dec, "z": args.z, "programs": [],
           "models": []}
    text = yamlio.dump_cluster(rec)
    text += ("\n# Add designations, programs and models, e.g.\n"
             "# designations:\n#   - ACT-CL J...\n"
             "# models:\n#   - title: Author et al. (2026)\n#     refs: [2026ApJ...999....1A]\n"
             "#     availability: public\n#     links:\n#       - label: Model download\n"
             "#         url: https://...\n")
    path.write_text(text, encoding="utf-8")
    print(f"created {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
