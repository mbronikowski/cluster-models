#!/usr/bin/env python3
"""Check external links in the data files, politely.

    python tools/check_links.py --changed-since origin/master   # only links added on a branch
    python tools/check_links.py --all                           # every link (manual runs only)

One request at a time, at most one request per host every --delay seconds
(default 3), HEAD first and a small GET only if HEAD is refused. ADS/arXiv/DOI
links generated from references are not checked. FTP links are listed, not
fetched. Exit status is 0 unless --strict is given and a link is broken.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cmdb.data import load_database  # noqa: E402

URL_RE = re.compile(r"(?:https?|ftp)://[^\s)\"'<>\]]+")
SKIP_HOSTS = {"ui.adsabs.harvard.edu", "arxiv.org", "doi.org", "scixplorer.org"}
USER_AGENT = ("cluster-models link check (+https://github.com/mbronikowski/cluster-models; "
              "one request per host every few seconds)")


def urls_in(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not str(k).startswith("_"):
                yield from urls_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from urls_in(v)
    elif isinstance(obj, str):
        for u in URL_RE.findall(obj):
            yield u.rstrip(".,;")


def all_urls() -> dict[str, set[str]]:
    db = load_database()
    found = defaultdict(set)
    for rec in db.clusters + db.transients:
        for u in urls_in(rec):
            found[u].add(rec["_file"])
    for u in urls_in(db.programs):
        found[u].add("data/programs.yaml")
    return found


def changed_urls(base: str) -> set[str]:
    diff = subprocess.run(["git", "diff", "--unified=0", f"{base}...HEAD", "--", "data/"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    out = set()
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out.update(u.rstrip(".,;") for u in URL_RE.findall(line))
    return out


def check(url: str, timeout: float) -> tuple[str, str]:
    if url.startswith("ftp://"):
        return "skipped", "FTP links are not checked"
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=dict(headers, **(
            {"Range": "bytes=0-1023"} if method == "GET" else {})))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return "ok", f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (400, 403, 405, 406, 501):
                continue
            if exc.code in (401, 403, 429):
                return "blocked", f"HTTP {exc.code} (refused or rate-limited; may still work in a browser)"
            return "broken", f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return "unreachable", str(getattr(exc, "reason", exc))
    return "broken", "no usable response"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check external links in data/ politely")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="check every link")
    g.add_argument("--changed-since", metavar="GITREF", help="only links added since GITREF")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between requests to one host")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--strict", action="store_true", help="exit 1 if a link is broken")
    args = ap.parse_args(argv)

    where = all_urls()
    targets = sorted(where) if args.all else sorted(changed_urls(args.changed_since) & set(where))
    targets = [u for u in targets if urllib.parse.urlparse(u).hostname not in SKIP_HOSTS]
    print(f"Checking {len(targets)} link(s) on "
          f"{len({urllib.parse.urlparse(u).hostname for u in targets})} host(s)")
    last = {}
    results = defaultdict(list)
    for u in targets:
        host = urllib.parse.urlparse(u).hostname
        wait = args.delay - (time.monotonic() - last.get(host, -1e9))
        if wait > 0:
            time.sleep(wait)
        status, detail = check(u, args.timeout)
        last[host] = time.monotonic()
        results[status].append((u, detail))
        if status != "ok":
            files = ", ".join(sorted(where.get(u, [])))
            msg = f"{status}: {u} ({detail}) in {files}"
            print(f"::warning::{msg}" if status in ("broken", "unreachable") else msg)
    print("\n" + ", ".join(f"{k}: {len(v)}" for k, v in sorted(results.items())) if results else "nothing to check")
    return 1 if args.strict and results.get("broken") else 0


if __name__ == "__main__":
    sys.exit(main())
