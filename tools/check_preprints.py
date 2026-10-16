#!/usr/bin/env python3
"""List arXiv references in the data that have since been published.

    python tools/check_preprints.py

Asks the arXiv API (one request per 50 preprints) for the journal reference and
DOI of every arXiv bibcode (YYYYarXivNNNNNNNNNX) or arXiv:NNNN.NNNNN reference.
Nothing is changed: replace a reference by hand, e.g. with doi:10.xxxx/...
or the published ADS bibcode.
"""

from __future__ import annotations

import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cmdb.data import load_database  # noqa: E402

NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def arxiv_id(ref: str):
    m = re.match(r"^\d{4}arXiv(\d{4})(\d{4,5})[A-Z.]$", ref)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    if ref.startswith("arXiv:"):
        return ref[6:]
    return None


def main() -> int:
    db = load_database()
    refs = {}
    for c in db.clusters:
        for m in c.get("models", []):
            for r in m.get("refs", []):
                refs.setdefault(r, set()).add(c["_file"])
    for t in db.transients:
        for r in t.get("refs", []):
            refs.setdefault(r, set()).add(t["_file"])
    ids = {r: arxiv_id(r) for r in refs if arxiv_id(r)}
    print(f"{len(ids)} preprint reference(s)")
    found = {}
    todo = sorted(set(ids.values()))
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        url = "https://export.arxiv.org/api/query?max_results=50&id_list=" + ",".join(chunk)
        req = urllib.request.Request(url, headers={"User-Agent": "cluster-models preprint check"})
        root = ET.fromstring(urllib.request.urlopen(req, timeout=60).read())
        for e in root.findall("a:entry", NS):
            aid = e.find("a:id", NS).text.rsplit("/", 1)[-1].split("v")[0]
            jr, doi = e.find("arxiv:journal_ref", NS), e.find("arxiv:doi", NS)
            if jr is not None or doi is not None:
                found[aid] = (jr.text if jr is not None else "", doi.text if doi is not None else "")
        time.sleep(3)
    for ref, aid in sorted(ids.items()):
        if aid in found:
            jr, doi = found[aid]
            print(f"{ref}: published as {jr or '?'}" + (f" (use doi:{doi})" if doi else "")
                  + f"  [{', '.join(sorted(refs[ref]))}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
