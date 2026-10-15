#!/usr/bin/env python3
"""Replace every page of the old GitHub wiki with a short "moved" notice.

Run this once the website is live:

    git clone https://github.com/mbronikowski/cluster-models.wiki.git /tmp/wiki
    python tools/wiki_moved_stubs.py /tmp/wiki
    cd /tmp/wiki && git commit -am "Wiki moved to GitHub Pages" && git push

Each cluster page points to its new page; everything else points to the site.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cmdb.data import load_database  # noqa: E402
from cmdb.site import load_config  # noqa: E402
from cmdb.text import clean_lookalikes, slugify  # noqa: E402


def wiki_key(stem: str) -> str:
    """Wiki file names write '+' and ' ' as '-' and use Unicode hyphens."""
    return re.sub(r"[^a-z0-9.]", "", clean_lookalikes(stem)[0].lower())


def main() -> int:
    wiki = Path(sys.argv[1])
    site = load_config()["url"]
    db = load_database()
    by_key = {}
    for c in db.clusters:
        by_key[re.sub(r"[^a-z0-9.]", "", c["name"].lower().replace("+", "-"))] = c["_slug"]
    # the migration renamed two pages
    by_key["ms1008.11224"] = slugify("MS 1008.1-1224")
    by_key["emacsj1341.92442"] = slugify("eMACS J1341.9-2442")
    n = 0
    for page in sorted(wiki.glob("*.md")):
        if page.stem.startswith("_"):
            target, label = site, "the cluster-models website"
        elif page.stem == "Home":
            target, label = site, "the cluster-models website"
        elif page.stem == "Program-list":
            target, label = site + "programs/", "the programs page"
        else:
            slug = by_key.get(wiki_key(page.stem))
            if slug is None:
                print(f"no cluster found for {page.name}; pointing to the home page")
                target, label = site, "the cluster-models website"
            else:
                target, label = f"{site}clusters/{slug}.html", "its new page"
        page.write_text(
            f"# This page has moved\n\nThe cluster-models wiki is now a website: "
            f"[{label}]({target}).\n\nThe data are maintained in "
            f"[the repository](https://github.com/mbronikowski/cluster-models/tree/master/data); "
            f"see the website for how to contribute.\n", encoding="utf-8")
        n += 1
    print(f"rewrote {n} wiki pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
