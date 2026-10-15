#!/usr/bin/env python3
"""Replace look-alike characters (Unicode dashes and minus signs, curly quotes,
non-breaking and zero-width spaces, ...) with their ASCII equivalents in the
data files, in place. Only those characters change; comments and layout are kept.

    python tools/fix_characters.py            # fix every file under data/
    python tools/fix_characters.py FILE ...   # fix the given files
    python tools/fix_characters.py --check    # report only, change nothing
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cmdb.text import char_name, clean_lookalikes  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args(argv)
    files = args.files or sorted((ROOT / "data").rglob("*.yaml"))
    total = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        new, changes = clean_lookalikes(text)
        if not changes:
            continue
        total += len(changes)
        counts = Counter(char_name(a) for a, _ in changes)
        print(f"{path}: " + "; ".join(f"{n} x{k}" for n, k in counts.items()))
        if not args.check:
            path.write_text(new, encoding="utf-8")
    verb = "found" if args.check else "replaced"
    print(f"{total} look-alike character(s) {verb}")
    return 1 if (args.check and total) else 0


if __name__ == "__main__":
    sys.exit(main())
