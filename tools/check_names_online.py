#!/usr/bin/env python3
"""Cross-check every cluster name against CDS Sesame (SIMBAD, then NED, then VizieR).

Not part of CI: it sends one request per name, one per second by default, and
caches answers in .cache/sesame.json so repeated runs only ask about new names.

    python tools/check_names_online.py                 # all clusters
    python tools/check_names_online.py abell-2744      # selected cluster files (slugs)
    python tools/check_names_online.py --report out.md # also write a Markdown report

Flags names that do not resolve, resolve far from the cluster position, or
whose SIMBAD redshift differs from ours, and lists SIMBAD aliases that are not
in our files (suggestions only: SIMBAD/NED cross-identifications can be wrong).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cmdb.catalogues import identify, search_key  # noqa: E402
from cmdb.coords import parse_dec, parse_ra, separation  # noqa: E402
from cmdb.data import load_database  # noqa: E402

SESAME = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxI/SNV?"
CACHE = ROOT / ".cache" / "sesame.json"
USER_AGENT = "cluster-models name check (https://github.com/mbronikowski/cluster-models)"


def query(name: str, delay: float, cache: dict) -> dict:
    if name in cache:
        return cache[name]
    xml = None
    for attempt in range(3):          # the service sometimes resets connections; back off
        time.sleep(delay * (1 + 4 * attempt))
        req = urllib.request.Request(SESAME + urllib.parse.quote(name), headers={"User-Agent": USER_AGENT})
        try:
            xml = urllib.request.urlopen(req, timeout=60).read()
            break
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
    if xml is None:
        return {"error": err}
    out = {"resolved": False}
    root = ET.fromstring(xml)
    for res in root.iter("Resolver"):
        ra, de = res.findtext("jradeg"), res.findtext("jdedeg")
        if ra is None or de is None:
            continue
        z = res.find("z")
        out = {
            "resolved": True, "resolver": res.get("name", "")[:1],
            "ra": float(ra), "dec": float(de), "oname": (res.findtext("oname") or "").strip(),
            "otype": res.findtext("otype"), "z": float(z.findtext("v")) if z is not None and z.findtext("v") else None,
            "aliases": [a.text.strip() for a in res.findall("alias") if a.text],
        }
        break
    cache[name] = out
    return out


def simbad_key(name: str) -> str:
    """Comparable key across our spelling and SIMBAD's (MCS = MACS, ACO = Abell...)."""
    s = name.upper().replace("MCS J", "MACS J").replace("ACO S ", "ABELL S").replace("ACO ", "ABELL ")
    s = s.replace("NAME ", "")
    return search_key(s)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cross-check names with CDS Sesame")
    ap.add_argument("slugs", nargs="*", help="cluster file names without .yaml (default: all)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (default 1)")
    ap.add_argument("--far", type=float, default=3.0, help="arcmin beyond which a match is flagged")
    ap.add_argument("--report", help="write a Markdown report to this file")
    args = ap.parse_args(argv)

    db = load_database()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    clusters = [c for c in db.clusters if not args.slugs or c["_slug"] in args.slugs]
    lines = ["# Name cross-check against CDS Sesame", ""]
    n_flags = 0
    try:
        for c in clusters:
            ra, dec = parse_ra(c["ra"]), parse_dec(c["dec"])
            names = [c["name"]] + c.get("aka", []) + c.get("designations", []) + c.get("common_names", [])
            flags, simbad_aliases, ours = [], set(), {simbad_key(n) for n in names}
            for n in names:
                r = query(n, args.delay, cache)
                if r.get("error"):
                    flags.append(f"`{n}`: query failed ({r['error']})")
                    continue
                if not r.get("resolved"):
                    flags.append(f"`{n}`: not found in SIMBAD/NED/VizieR")
                    continue
                sep = separation(ra, dec, r["ra"], r["dec"]) * 60
                hits = identify(n, db.catalogues)
                tol = max(args.far, hits[0].pattern.tolerance if hits else 0)
                if sep > tol:
                    flags.append(f"`{n}`: resolves to {r['oname']} ({r['otype']}, via {r['resolver']}) "
                                 f"{sep:.1f}' away")
                if r["resolver"] == "S" and r.get("z") is not None and abs(r["z"] - c["z"]) > 0.01 \
                        and r.get("otype") in ("ClG", "GrG", "CGG", "PCG", "SCG"):
                    flags.append(f"`{n}`: SIMBAD z = {r['z']} vs ours {c['z']}")
                if r["resolver"] == "S" and sep < tol:
                    simbad_aliases.update(r.get("aliases", []))
            named = sorted(a[5:] for a in simbad_aliases if a.startswith("NAME "))
            if flags or named:
                lines.append(f"## {c['name']} (`{c['_file']}`)")
                lines.extend(f"- {f}" for f in flags)
                if named:
                    lines.append(f"- SIMBAD common name(s): {', '.join(named)}")
                lines.append("")
                n_flags += len(flags)
                print(f"{c['name']}: " + "; ".join(flags + ([f"SIMBAD NAME {named}"] if named else [])))
            c["_simbad_aliases"] = sorted(a for a in simbad_aliases if simbad_key(a) not in ours)
    finally:
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True))
    sugg = [(c["name"], c.get("_simbad_aliases", [])) for c in clusters if c.get("_simbad_aliases")]
    if sugg:
        lines += ["## SIMBAD aliases not in our files (suggestions, verify before adding)", ""]
        for name, al in sugg:
            lines.append(f"- **{name}**: " + "; ".join(f"`{a}`" for a in al))
    if args.report:
        Path(args.report).write_text("\n".join(lines) + "\n")
    print(f"\n{len(clusters)} clusters checked, {n_flags} flag(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
