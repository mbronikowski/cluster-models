"""Derived data and HTML rendering for the static site."""

from __future__ import annotations

import csv
import datetime as dt
import html
import io
import json
import math
import re
import shutil
import subprocess
import urllib.parse
from collections import defaultdict
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

from . import ROOT
from .catalogues import TYPE_LABELS, identify, search_keys
from .coords import format_dec, format_ra, galactic_to_icrs, parse_dec, parse_ra, separation
from .data import Database, strip_private
from .text import anchor_id

ALADIN_JS = "https://aladin.cds.unistra.fr/AladinLite/api/v3/3.8.2/aladin.js"
NEIGHBOUR_RADIUS_DEG = 2.0

AVAILABILITY = {
    "public": ("Public", "Model files can be downloaded"),
    "on-request": ("On request", "The authors share the model on request"),
    "upcoming": ("Release announced", "Release announced but not yet available"),
    "defunct": ("Link defunct", "Was published, but the download link no longer works"),
    "unavailable": ("Not released", "Explicitly not released"),
    "unknown": ("Not stated", "Availability not stated"),
}
TYPE_ORDER = ["sz", "xray", "optical", "lens", "source", "galaxy", "other"]


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


# --- references ----------------------------------------------------------------------------

def ref_url(ref: str) -> str:
    if ref.startswith("arXiv:"):
        return "https://arxiv.org/abs/" + ref[6:]
    if ref.startswith("doi:"):
        return "https://doi.org/" + ref[4:]
    return "https://ui.adsabs.harvard.edu/abs/" + urllib.parse.quote(ref, safe="") + "/abstract"


def ref_fallback_label(ref: str) -> str:
    if ref.startswith(("arXiv:", "doi:")):
        return ref
    year, journal = ref[:4], ref[4:9].strip(".")
    vol, page = ref[9:13].strip("."), ref[14:18].strip(".")
    return f"{journal} {vol}, {page} ({year})" if journal != "arXiv" else f"arXiv ({year})"


# --- Markdown -----------------------------------------------------------------------------------

_MD = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
_LINK = re.compile(r"\]\(([a-z]+):([^)\s]+)\)")


def render_md(text: str, root: str, slug_of_cluster=None) -> str:
    if not text:
        return ""

    def repl(m):
        scheme, rest = m.group(1), m.group(2)
        if scheme == "ref":
            return f"]({ref_url(rest)})"
        if scheme == "cluster":
            return f"]({root}clusters/{rest}.html)"
        if scheme == "program":
            return f"]({root}programs/{rest}.html)"
        if scheme == "transient":
            return f"]({root}transients/{rest}.html)"
        return m.group(0)

    return _MD.render(_LINK.sub(repl, text)).strip()


# --- sky map (Mollweide, equatorial, RA increasing to the left) ---------------------------------
# Centred on RA = 6h so the map edge (RA = 18h) falls in the emptiest stretch of the
# catalogue, behind the Galactic centre.

MAP_W, MAP_H = 960.0, 480.0
MAP_CENTER_RA = 90.0


def mollweide(ra: float, dec: float):
    lam = math.radians(((MAP_CENTER_RA - ra) + 180.0) % 360.0 - 180.0)  # RA grows leftwards
    phi = math.radians(dec)
    if abs(abs(phi) - math.pi / 2) < 1e-9:
        theta = phi
    else:
        theta = phi
        for _ in range(50):
            f = 2 * theta + math.sin(2 * theta) - math.pi * math.sin(phi)
            d = 2 + 2 * math.cos(2 * theta)
            if abs(d) < 1e-12:
                break
            step = f / d
            theta -= step
            if abs(step) < 1e-10:
                break
    x = (2 * math.sqrt(2) / math.pi) * lam * math.cos(theta)
    y = math.sqrt(2) * math.sin(theta)
    # x in [-2*sqrt2, 2*sqrt2], y in [-sqrt2, sqrt2]
    sx = MAP_W / 2 + x * (MAP_W / 2) / (2 * math.sqrt(2))
    sy = MAP_H / 2 - y * (MAP_H / 2) / math.sqrt(2)
    return round(sx, 1), round(sy, 1)


def _polyline_segments(points):
    """Split a list of projected points where it jumps across the map edge."""
    segs, cur = [], []
    for p in points:
        if cur and abs(p[0] - cur[-1][0]) > MAP_W / 3:
            segs.append(cur)
            cur = []
        cur.append(p)
    if cur:
        segs.append(cur)
    return ["M" + " L".join(f"{x},{y}" for x, y in s) for s in segs if len(s) > 1]


def _sweep():
    """RA values sweeping the map from the left edge to the right edge."""
    return [MAP_CENTER_RA + 179.99 - i * 359.98 / 360 for i in range(361)]


def sky_map_geometry():
    grid = []
    edge = (MAP_CENTER_RA + 180) % 360
    for dec in (-60, -30, 0, 30, 60):
        grid += _polyline_segments([mollweide(ra, dec) for ra in _sweep()])
    for ra in range(0, 360, 30):
        if ra == edge:
            continue
        grid += _polyline_segments([mollweide(ra, d / 2) for d in range(-180, 181)])
    outline = []
    for side in (MAP_CENTER_RA + 180 - 1e-6, MAP_CENTER_RA - 180 + 1e-6):
        outline.append([mollweide(side, d / 2) for d in range(-180, 181)])
    outline_path = "M" + " L".join(f"{x},{y}" for x, y in outline[0]) + " L" + " L".join(
        f"{x},{y}" for x, y in reversed(outline[1])) + " Z"
    gal = [mollweide(*galactic_to_icrs(l / 2, 0.0)) for l in range(0, 721)]
    galactic = _polyline_segments(gal)
    ra_labels = []
    for h in range(0, 24, 2):
        if h * 15 == edge:
            continue
        x, y = mollweide(h * 15.0, 0.0)
        ra_labels.append({"x": x, "y": y, "text": f"{h}h"})
    dec_labels = []
    for dec in (-60, -30, 0, 30, 60):
        x, y = mollweide(MAP_CENTER_RA + 180 - 0.001, dec)
        dec_labels.append({"x": x, "y": y, "text": f"{dec:+d}°" if dec else "0°"})
    lx, ly = mollweide(*galactic_to_icrs(128.0, 0.0))
    return {"grid": grid, "outline": outline_path, "galactic": galactic, "ra_labels": ra_labels,
            "dec_labels": dec_labels, "galactic_label": {"x": lx, "y": ly}}


# --- derived records ------------------------------------------------------------------------

def coordinate_links(ra: float, dec: float):
    r, d = f"{ra:.5f}", f"{dec:.5f}"   # never a '+' in URLs: positive Dec is written unsigned
    q = urllib.parse.quote
    return [
        ("SIMBAD", f"https://simbad.cds.unistra.fr/simbad/sim-coo?Coord={q(r + ' ' + d)}&CooFrame=ICRS"
                   f"&CooEpoch=2000&CooEqui=2000&Radius=2&Radius.unit=arcmin&submit=submit+query"),
        ("NED", f"https://ned.ipac.caltech.edu/conesearch?search_type=Near%20Position%20Search"
                f"&in_csys=Equatorial&in_equinox=J2000&ra={r}&dec={d}&radius=2"),
        ("MAST", f"https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html?searchQuery={q(r + ' ' + d)}"),
        ("ESASky", f"https://sky.esa.int/esasky/?target={q(r + ' ' + d)}&fov=0.15&cooframe=J2000&sci=true"),
    ]


class Site:
    def __init__(self, db: Database, out: Path, config: dict):
        self.db = db
        self.out = out
        self.cfg = config
        self.env = Environment(
            loader=FileSystemLoader(str(ROOT / "templates")),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True, lstrip_blocks=True,
        )
        self.env.globals.update(cfg=config, availability=AVAILABILITY)
        self.env.filters["md"] = render_md
        self.env.filters["ref_url"] = ref_url
        self.env.filters["natural"] = natural_key
        try:
            commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout.strip()
        except Exception:  # noqa: BLE001
            commit = ""
        self.env.globals["build"] = {
            "date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
            "commit": commit,
        }
        self.prepare()

    # ------------------------------------------------------------------ data
    def ref(self, rid: str) -> dict:
        meta = self.db.references.get(rid) or {}
        return {"id": rid, "url": ref_url(rid), "label": meta.get("label") or ref_fallback_label(rid),
                "title": meta.get("title"), "published": meta.get("published"), "doi": meta.get("doi")}

    def prepare(self):
        db = self.db
        self.programs = {p["id"]: dict(p, members=[], overview_ref=self.ref(p["overview"]) if p.get("overview") else None)
                         for p in db.programs}
        voc = db.vocabulary
        trans_by_cluster = defaultdict(list)
        cats = {c.id: c for c in db.catalogues}
        clusters = []
        for c in sorted(db.clusters, key=lambda c: natural_key(c["name"])):
            ra, dec = parse_ra(c["ra"]), parse_dec(c["dec"])
            names = [c["name"]] + c.get("aka", []) + c.get("designations", [])
            groups = defaultdict(list)
            catalogue_ids = []
            for n in names:
                hit = identify(n, db.catalogues)[0]
                groups[hit.type].append({"name": n, "cat": hit.catalogue})
                if hit.catalogue.id not in catalogue_ids:
                    catalogue_ids.append(hit.catalogue.id)
            desig_groups = [{"type": t, "label": TYPE_LABELS[t], "items": groups[t]}
                            for t in TYPE_ORDER if groups.get(t)]
            models = []
            for m in c.get("models", []):
                rec = dict(m)
                rec["anchor"] = anchor_id(m["title"])
                rec["refs"] = [self.ref(r) for r in m.get("refs", [])]
                rec["availability"] = m.get("availability", "unknown")
                rec["status"] = m.get("status", "current")
                rec["program_obj"] = self.programs.get(m.get("program"))
                rec["tag_desc"] = {t: voc.get("tags", {}).get(t, "") for t in m.get("tags", [])}
                models.append(rec)
            for rec in models:
                sb = rec.get("superseded_by")
                if sb:
                    tgt = next((x for x in models if sb in [r["id"] for r in x["refs"]]
                                or x["anchor"] == anchor_id(sb)), None)
                    rec["superseded_by_model"] = tgt
            keys = []
            for n in names + c.get("common_names", []):
                keys.extend(search_keys(n))
            rec = {
                "slug": c["_slug"], "file": c["_file"], "name": c["name"],
                "common_names": c.get("common_names", []), "aka": c.get("aka", []),
                "designations": c.get("designations", []), "all_names": names,
                "desig_groups": desig_groups, "catalogue_ids": catalogue_ids,
                "ra": c["ra"], "dec": c["dec"], "ra_deg": ra, "dec_deg": dec, "z": c["z"],
                "programs": [self.programs[p] for p in c.get("programs", [])],
                "program_ids": c.get("programs", []),
                "image": c.get("image"), "links": c.get("links", []), "models": models,
                "observations": c.get("observations", []), "notes": c.get("notes", ""),
                "search_keys": sorted(set(keys)),
                "n_models": len(models),
                "n_current": sum(1 for m in models if m["status"] != "superseded"),
                "has_public": any(m["availability"] == "public" for m in models),
                "has_jwst": any("JWST" in m.get("data", []) for m in models),
                "coord_links": coordinate_links(ra, dec),
                "map_xy": mollweide(ra, dec),
                "raw": strip_private(c),
            }
            clusters.append(rec)
        self.clusters = clusters
        self.by_slug = {c["slug"]: c for c in clusters}
        for c in clusters:
            for p in c["programs"]:
                p["members"].append(c)
        # transients
        transients = []
        for t in sorted(db.transients, key=lambda t: natural_key(t["name"])):
            rec = dict(strip_private(t))
            rec["slug"] = t["_slug"]
            rec["file"] = t["_file"]
            rec["cluster_obj"] = self.by_slug.get(t["cluster"])
            rec["refs_obj"] = [self.ref(r) for r in t.get("refs", [])]
            rec["class_label"] = voc.get("transient_class", {}).get(t["class"], t["class"])
            rec["class_label"] = {"agn": "AGN"}.get(t["class"], rec["class_label"])
            rec["images"] = t.get("images", "multiple")
            transients.append(rec)
            trans_by_cluster[t["cluster"]].append(rec)
        self.transients = transients
        for c in clusters:
            c["transients"] = trans_by_cluster.get(c["slug"], [])
        # neighbours
        for c in clusters:
            near = []
            for o in clusters:
                if o is c:
                    continue
                s = separation(c["ra_deg"], c["dec_deg"], o["ra_deg"], o["dec_deg"])
                near.append((s, o))
            near.sort(key=lambda x: x[0])
            within = [(s, o) for s, o in near if s <= NEIGHBOUR_RADIUS_DEG]
            c["neighbours"] = [{"sep_arcmin": s * 60, "cluster": o} for s, o in within]
            c["nearest"] = {"sep_arcmin": near[0][0] * 60, "cluster": near[0][1]} if not within else None
        # catalogue index
        index = defaultdict(list)
        for c in clusters:
            for g in c["desig_groups"]:
                for item in g["items"]:
                    index[item["cat"].id].append({"name": item["name"], "cluster": c})
        self.catalogue_index = []
        for t in TYPE_ORDER:
            cats_t = [cat for cat in db.catalogues if cat.type == t or
                      any(p.type == t for p in cat.patterns)]
            entries = []
            for cat in sorted(cats_t, key=lambda x: x.label.lower()):
                items = [i for i in index.get(cat.id, [])
                         if identify(i["name"], db.catalogues)[0].type == t]
                if items:
                    items.sort(key=lambda i: natural_key(i["name"]))
                    entries.append({"cat": cat, "items": items})
            if entries:
                self.catalogue_index.append({"type": t, "label": TYPE_LABELS[t], "catalogues": entries})
        self.n_designations = sum(len(c["all_names"]) for c in clusters)

    # ------------------------------------------------------------------ output
    def write(self, rel: str, text: str):
        path = self.out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def render(self, template: str, rel: str, **ctx):
        depth = rel.count("/")
        root = "../" * depth
        ctx.setdefault("page_path", rel)
        self.write(rel, self.env.get_template(template).render(root=root, **ctx))

    def index_json(self):
        rows = []
        for c in self.clusters:
            rows.append({
                "s": c["slug"], "n": c["name"], "cn": c["common_names"], "aka": c["aka"],
                "ra": round(c["ra_deg"], 6), "dec": round(c["dec_deg"], 6),
                "rs": c["ra"], "ds": c["dec"], "z": c["z"], "k": c["search_keys"],
                "m": c["n_models"], "pub": c["has_public"], "jw": c["has_jwst"],
                "p": c["program_ids"], "cat": c["catalogue_ids"],
                "t": [t["class"] for t in c["transients"]],
            })
        return rows

    def build(self):
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        shutil.copytree(ROOT / "static", self.out / "static")
        (self.out / ".nojekyll").write_text("")
        programs_sorted = sorted(self.programs.values(), key=lambda p: (p["kind"] != "survey", p["short"].lower()))
        stats = {
            "clusters": len(self.clusters),
            "models": sum(c["n_models"] for c in self.clusters),
            "transients": len(self.transients),
            "programs": sum(1 for p in self.programs.values() if p["kind"] == "survey"),
        }
        common = dict(stats=stats, programs_sorted=programs_sorted)
        idx = self.index_json()
        index_data = json.dumps(idx, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
        self.render("index.html", "index.html", clusters=self.clusters, index_data=index_data,
            map=sky_map_geometry(),
            catalogues=[cat for cat in self.db.catalogues], **common)
        for c in self.clusters:
            self.render("cluster.html", f"clusters/{c['slug']}.html", c=c, aladin_js=ALADIN_JS, **common)
        self.render("programs.html", "programs/index.html", **common)
        for p in self.programs.values():
            self.render("program.html", f"programs/{p['id']}.html", p=p, **common)
        self.render("transients.html", "transients/index.html", transients=self.transients, **common)
        for t in self.transients:
            self.render("transient.html", f"transients/{t['slug']}.html", t=t, **common)
        self.render("catalogues.html", "catalogues.html", index=self.catalogue_index,
                    n_designations=self.n_designations, **common)
        self.render("about.html", "about.html", **common)
        self.render("404.html", "404.html", **common)
        self.write_exports(idx)
        self.write_sitemap()

    # ------------------------------------------------------------------ exports
    def write_exports(self, idx):
        d = "data/"
        full = {
            "generated": self.env.globals["build"]["date"],
            "licence": "CC-BY-4.0",
            "source": self.cfg["repo"],
            "clusters": [c["raw"] for c in self.clusters],
            "transients": [strip_private(t) for t in self.db.transients],
            "programs": self.db.programs,
            "references": self.db.references,
        }
        self.write(d + "catalogue.json", json.dumps(full, indent=1, ensure_ascii=False))
        for c in self.clusters:
            self.write(f"{d}clusters/{c['slug']}.json", json.dumps(c["raw"], indent=1, ensure_ascii=False))
            shutil.copyfile(ROOT / c["file"], self.out / d / "clusters" / f"{c['slug']}.yaml")
        # flat cluster table
        cols = ["name", "common_names", "aka", "designations", "ra", "dec", "ra_deg", "dec_deg", "z",
                "n_models", "has_public_model", "has_jwst_model", "programs", "lensed_sources", "url"]
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(cols)
        for c in self.clusters:
            w.writerow([c["name"], "; ".join(c["common_names"]), "; ".join(c["aka"]),
                        "; ".join(c["designations"]), c["ra"], c["dec"], f"{c['ra_deg']:.6f}",
                        f"{c['dec_deg']:.6f}", c["z"], c["n_models"], int(c["has_public"]),
                        int(c["has_jwst"]), "; ".join(c["program_ids"]),
                        "; ".join(t["name"] for t in c["transients"]),
                        f"{self.cfg['url']}clusters/{c['slug']}.html"])
        self.write(d + "clusters.csv", buf.getvalue())
        # ECSV (readable by astropy.table.Table.read)
        header = [
            "# %ECSV 1.0", "# ---", "# datatype:",
            "# - {name: name, datatype: string}",
            "# - {name: ra, unit: deg, datatype: float64, description: J2000 right ascension}",
            "# - {name: dec, unit: deg, datatype: float64, description: J2000 declination}",
            "# - {name: z, datatype: float64, description: cluster redshift}",
            "# - {name: n_models, datatype: int64}",
            "# - {name: has_public_model, datatype: bool}",
            "# - {name: has_jwst_model, datatype: bool}",
            "# - {name: programs, datatype: string}",
            "# - {name: slug, datatype: string}",
            "# meta: {source: '" + self.cfg["url"] + "', licence: CC-BY-4.0}",
            "# schema: astropy-2.0",
            "name ra dec z n_models has_public_model has_jwst_model programs slug",
        ]
        lines = list(header)
        for c in self.clusters:
            progs = ";".join(c["program_ids"])
            lines.append(" ".join([json.dumps(c["name"]), f"{c['ra_deg']:.6f}", f"{c['dec_deg']:.6f}",
                                   repr(c["z"]), str(c["n_models"]), str(c["has_public"]),
                                   str(c["has_jwst"]), json.dumps(progs), c["slug"]]))
        self.write(d + "clusters.ecsv", "\n".join(lines) + "\n")
        # one row per model
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["cluster", "cluster_slug", "title", "program", "refs", "data", "software",
                    "availability", "status", "links", "note_urls"])
        for c in self.clusters:
            for m in c["models"]:
                note_urls = re.findall(r"\]\(((?:https?|ftp)://[^)\s]+)\)", m.get("note", ""))
                w.writerow([c["name"], c["slug"], m["title"], m.get("program", ""),
                            "; ".join(r["id"] for r in m["refs"]), "; ".join(m.get("data", [])),
                            m.get("software", ""), m["availability"], m["status"],
                            "; ".join(l["url"] for l in m.get("links", [])), "; ".join(note_urls)])
        self.write(d + "models.csv", buf.getvalue())
        self.write(d + "programs.json", json.dumps(self.db.programs, indent=1, ensure_ascii=False))
        self.write(d + "transients.json", json.dumps([strip_private(t) for t in self.db.transients],
                                                       indent=1, ensure_ascii=False))
        self.write(d + "search-index.json", json.dumps(idx, separators=(",", ":")))

    def write_sitemap(self):
        base = self.cfg["url"]
        pages = ["", "programs/", "transients/", "catalogues.html", "about.html"]
        pages += [f"clusters/{c['slug']}.html" for c in self.clusters]
        pages += [f"programs/{p}.html" for p in self.programs]
        pages += [f"transients/{t['slug']}.html" for t in self.transients]
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        xml += [f"  <url><loc>{html.escape(base + p)}</loc></url>" for p in pages]
        xml.append("</urlset>")
        self.write("sitemap.xml", "\n".join(xml) + "\n")
        self.write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n")


def load_config() -> dict:
    with open(ROOT / "site.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
