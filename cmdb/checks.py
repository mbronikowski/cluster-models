"""Validation rules. `validate.py` runs these; the build refuses to run on errors."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field

import jsonschema

from . import ROOT
from .catalogues import identify, position_excess, search_key
from .coords import parse_dec, parse_ra
from .data import Database, strip_private
from .text import anchor_id, prose_problems, slugify, strict_ascii_problems

MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
REF_RE = re.compile(r"^(\d{4}[A-Za-z0-9&.]{14}[A-Za-z.]|arXiv:\d{4}\.\d{4,5}|doi:10\.\d{4,9}/\S+)$")


@dataclass
class Report:
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)

    def error(self, where: str, msg: str):
        self.errors.append((where, msg))

    def warn(self, where: str, msg: str):
        self.warnings.append((where, msg))


def _schema(name):
    with open(ROOT / "schema" / f"{name}.schema.json", encoding="utf-8") as fh:
        return json.load(fh)


def _schema_errors(instance, schema):
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in err.absolute_path) or "(top level)"
        yield f"{path}: {err.message}"


# --- character rules -------------------------------------------------------------

# Keys whose values are identifiers (strict ASCII); everything else is prose.
STRICT_KEYS = {
    "name", "common_names", "aka", "designations", "ra", "dec", "programs", "program", "refs",
    "superseded_by", "data", "software", "availability", "status", "tags", "url",
    "ignore_position_check", "cluster", "aliases", "class", "id", "short", "kind",
    "facilities", "proposal", "archive", "overview", "facility", "instrument", "mode",
    "filters", "doi",
}


def _walk_strings(obj, key=None, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            yield from _walk_strings(v, k, f"{path}/{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, key, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield key, path, obj


def check_characters(where, obj, report, strict_name_key=True):
    for key, path, value in _walk_strings(obj):
        strict = key in STRICT_KEYS
        if key == "name" and not strict_name_key:
            strict = False
        problems = strict_ascii_problems(value) if strict else prose_problems(value)
        for p in problems:
            report.error(where, f"{path}: {p} in {value!r}")


# --- helpers ---------------------------------------------------------------------------

def _internal_links(text):
    for label, target in MD_LINK.findall(text or ""):
        yield label, target


def _check_links_in_text(where, text, db, report, anchors=None, field_name="note"):
    for label, target in _internal_links(text):
        scheme, _, rest = target.partition(":")
        if target.startswith("#"):
            if anchors is not None and target[1:] not in anchors:
                report.error(where, f"{field_name}: link '#{target[1:]}' does not match any "
                                    f"model on this page")
        elif scheme == "cluster":
            if rest not in db.cluster_by_slug:
                report.error(where, f"{field_name}: unknown cluster link 'cluster:{rest}'")
        elif scheme == "program":
            if rest not in db.program_by_id:
                report.error(where, f"{field_name}: unknown program link 'program:{rest}'")
        elif scheme == "transient":
            if rest not in {t['_slug'] for t in db.transients}:
                report.error(where, f"{field_name}: unknown transient link 'transient:{rest}'")
        elif scheme == "ref":
            if not REF_RE.match(rest):
                report.error(where, f"{field_name}: malformed reference link 'ref:{rest}'")
        elif scheme in ("http", "https", "ftp", "mailto"):
            if "adsabs.harvard.edu/abs/" in target:
                report.warn(where, f"{field_name}: ADS URL used as a link; write "
                                   f"[{label}](ref:<bibcode>) instead")
        else:
            report.error(where, f"{field_name}: unsupported link target {target!r} "
                                f"(use https://, ref:, cluster:, program:, transient: or #anchor)")


def _vocab(db, name):
    return set((db.vocabulary or {}).get(name, {}) or {})


# --- main entry point --------------------------------------------------------------------

def validate(db: Database) -> Report:
    report = Report()
    for where, msg in db.load_errors:
        report.error(where, msg)

    cluster_schema = _schema("cluster")
    transient_schema = _schema("transient")
    programs_schema = _schema("programs")

    check_registry(db, report)
    program_ids = set(db.program_by_id)

    # programs ----------------------------------------------------------------------
    for msg in _schema_errors(db.programs, programs_schema):
        report.error("data/programs.yaml", msg)
    check_characters("data/programs.yaml", db.programs, report, strict_name_key=False)
    seen = set()
    for p in db.programs if isinstance(db.programs, list) else []:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        if pid in seen:
            report.error("data/programs.yaml", f"duplicate program id {pid!r}")
        seen.add(pid)
        if p.get("kind") not in _vocab(db, "program_kind"):
            report.error("data/programs.yaml", f"{pid}: kind {p.get('kind')!r} not in vocabulary")
        for f in p.get("facilities", []):
            if f not in _vocab(db, "facility"):
                report.error("data/programs.yaml", f"{pid}: facility {f!r} not in vocabulary")
        _check_links_in_text("data/programs.yaml", p.get("note"), db, report, field_name=f"{pid} note")

    # references ----------------------------------------------------------------------------
    if not isinstance(db.references, dict):
        report.error("data/references.yaml", "must be a mapping of reference -> metadata")
    else:
        for ref, meta in db.references.items():
            if not REF_RE.match(str(ref)):
                report.error("data/references.yaml", f"malformed reference key {ref!r}")
            if meta is not None and not isinstance(meta, dict):
                report.error("data/references.yaml", f"{ref}: value must be a mapping")
                continue
            for k in (meta or {}):
                if k not in ("label", "title", "doi", "published"):
                    report.error("data/references.yaml", f"{ref}: unknown key {k!r}")
        check_characters("data/references.yaml", db.references, report, strict_name_key=False)
        for ref in db.references:
            for p in strict_ascii_problems(str(ref)):
                report.error("data/references.yaml", f"key {ref!r}: {p}")

    # clusters -------------------------------------------------------------------------------
    key_owner: dict[str, tuple[str, str]] = {}
    names_seen: dict[str, str] = {}
    for c in db.clusters:
        f = c["_file"]
        data = strip_private(c)
        errs = list(_schema_errors(data, cluster_schema))
        for msg in errs:
            report.error(f, msg)
        if errs:
            continue
        check_characters(f, data, report)
        name = c["name"]

        expected = slugify(name) + ".yaml"
        if f.rsplit("/", 1)[-1] != expected:
            report.error(f, f"file name must be {expected!r} for name {name!r}")
        if name in names_seen:
            report.error(f, f"duplicate cluster name (also in {names_seen[name]})")
        names_seen[name] = f

        try:
            ra = parse_ra(c["ra"])
            dec = parse_dec(c["dec"])
        except ValueError as exc:
            report.error(f, str(exc))
            continue

        # designations: catalogue, position, collisions
        all_names = [name] + list(c.get("aka", [])) + list(c.get("designations", []))
        ignore = set(c.get("ignore_position_check", []))
        for extra in ignore - set(all_names):
            report.error(f, f"ignore_position_check lists {extra!r}, which is not one of the names")
        local_keys: dict[str, str] = {}
        for n in all_names:
            hits = identify(n, db.catalogues)
            if not hits:
                report.error(f, f"designation {n!r} does not match any catalogue in "
                                f"data/catalogues.yaml (fix the spelling, add the catalogue, or "
                                f"move a nickname to common_names)")
            elif len({h.catalogue.id for h in hits}) > 1:
                report.error(f, f"designation {n!r} matches several catalogues: "
                                + ", ".join(h.catalogue.id for h in hits))
            else:
                h = hits[0]
                excess = position_excess(h, ra, dec)
                if excess is not None and excess > h.pattern.tolerance and n not in ignore:
                    report.error(f, f"designation {n!r} encodes a position {excess:.1f}' away from "
                                    f"ra/dec (tolerance {h.pattern.tolerance:g}' for {h.catalogue.label}); "
                                    f"check the coordinates or the designation")
            k = search_key(n)
            if k in local_keys:
                report.warn(f, f"{n!r} is the same designation as {local_keys[k]!r}")
            local_keys[k] = n
            if k in key_owner and key_owner[k][0] != f:
                report.error(f, f"designation {n!r} also belongs to {key_owner[k][0]}")
            key_owner.setdefault(k, (f, n))
        for cn in c.get("common_names", []):
            if identify(cn, db.catalogues):
                report.warn(f, f"common name {cn!r} looks like a catalogue designation "
                               f"(move it to designations?)")

        # programs
        for p in c.get("programs", []):
            if p not in program_ids:
                report.error(f, f"unknown program {p!r} (see data/programs.yaml)")
            elif db.program_by_id[p].get("kind") == "database":
                report.warn(f, f"program {p!r} is a database, not an observing program")

        # models
        anchors = {}
        refs_on_page = set()
        for i, m in enumerate(c.get("models", [])):
            a = anchor_id(m["title"])
            if a in anchors:
                report.error(f, f"models[{i}]: title {m['title']!r} duplicates another model's "
                                f"anchor '#{a}' (make titles distinct)")
            anchors[a] = m
            refs_on_page.update(m.get("refs", []))
        for i, m in enumerate(c.get("models", [])):
            where = f"{f} models[{i}] ({m['title']})"
            prog = m.get("program")
            if prog and prog not in program_ids:
                report.error(where, f"unknown program {prog!r}")
            elif prog and prog not in c.get("programs", []):
                report.error(where, f"program {prog!r} must also be listed in the cluster's programs")
            for d in m.get("data", []):
                if d not in _vocab(db, "data"):
                    report.error(where, f"data {d!r} not in data/vocabulary.yaml")
            for t in m.get("tags", []):
                if t not in _vocab(db, "tags"):
                    report.error(where, f"tag {t!r} not in data/vocabulary.yaml")
            if m.get("software") and m["software"] not in _vocab(db, "software"):
                report.error(where, f"software {m['software']!r} not in data/vocabulary.yaml")
            av = m.get("availability", "unknown")
            if av not in _vocab(db, "availability"):
                report.error(where, f"availability {av!r} not in data/vocabulary.yaml")
            st = m.get("status", "current")
            if st not in _vocab(db, "status"):
                report.error(where, f"status {st!r} not in data/vocabulary.yaml")
            sb = m.get("superseded_by")
            if sb:
                if st != "superseded":
                    report.error(where, "superseded_by given but status is not 'superseded'")
                if sb not in refs_on_page and anchor_id(sb) not in anchors:
                    report.error(where, f"superseded_by {sb!r} is neither a reference nor a model "
                                        f"title on this page")
            if av == "public" and not m.get("links") and not re.search(
                    r"\]\((https?|ftp)://", m.get("note", "")):
                report.warn(where, "availability is 'public' but no download link is given")
            for r in m.get("refs", []):
                if r not in db.references:
                    report.warn(where, f"reference {r} has no entry in data/references.yaml "
                                       f"(it will be shown by its identifier)")
            _check_links_in_text(where, m.get("note"), db, report, anchors)
        _check_links_in_text(f, c.get("notes"), db, report, anchors, field_name="notes")
        if c.get("image"):
            _check_links_in_text(f, c["image"].get("credit"), db, report, field_name="image credit")
        for i, o in enumerate(c.get("observations", [])):
            if o["facility"] not in _vocab(db, "facility"):
                report.error(f, f"observations[{i}]: facility {o['facility']!r} not in vocabulary")
            if o.get("program") and o["program"] not in program_ids:
                report.error(f, f"observations[{i}]: unknown program {o['program']!r}")

    # transients ---------------------------------------------------------------------------
    tnames = {}
    for t in db.transients:
        f = t["_file"]
        data = strip_private(t)
        errs = list(_schema_errors(data, transient_schema))
        for msg in errs:
            report.error(f, msg)
        if errs:
            continue
        check_characters(f, data, report)
        expected = slugify(t["name"]) + ".yaml"
        if f.rsplit("/", 1)[-1] != expected:
            report.error(f, f"file name must be {expected!r} for name {t['name']!r}")
        if t["name"] in tnames:
            report.error(f, f"duplicate transient name (also in {tnames[t['name']]})")
        tnames[t["name"]] = f
        if t["cluster"] not in db.cluster_by_slug:
            report.error(f, f"unknown cluster {t['cluster']!r} (use the cluster file name "
                            f"without .yaml)")
        if t["class"] not in _vocab(db, "transient_class"):
            report.error(f, f"class {t['class']!r} not in data/vocabulary.yaml")
        if t["status"] not in _vocab(db, "transient_status"):
            report.error(f, f"status {t['status']!r} not in data/vocabulary.yaml")
        if t.get("images", "multiple") not in _vocab(db, "transient_images"):
            report.error(f, f"images {t['images']!r} not in data/vocabulary.yaml")
        for r in t.get("refs", []):
            if r not in db.references:
                report.warn(f, f"reference {r} has no entry in data/references.yaml")
        _check_links_in_text(f, t.get("notes"), db, report, field_name="notes")

    # references used nowhere
    used = set()
    for c in db.clusters:
        for m in c.get("models", []) or []:
            used.update(m.get("refs", []) or [])
            used.update(r for _, r in _internal_links(m.get("note", "")) if r.startswith("ref:"))
    text_refs = set()
    for c in db.clusters:
        blobs = [c.get("notes", "")] + [m.get("note", "") for m in c.get("models", []) or []]
        for b in blobs:
            text_refs.update(t[4:] for _, t in _internal_links(b) if t.startswith("ref:"))
    for t in db.transients:
        used.update(t.get("refs", []) or [])
        text_refs.update(x[4:] for _, x in _internal_links(t.get("notes", "")) if x.startswith("ref:"))
    for p in db.programs if isinstance(db.programs, list) else []:
        if isinstance(p, dict) and p.get("overview"):
            used.add(p["overview"])
    for ref in db.references if isinstance(db.references, dict) else []:
        if ref not in used and ref not in text_refs:
            report.warn("data/references.yaml", f"{ref} is not used anywhere")
    return report


def check_registry(db: Database, report: Report):
    ids = set()
    for cat in db.catalogues:
        if cat.id in ids:
            report.error("data/catalogues.yaml", f"duplicate catalogue id {cat.id!r}")
        ids.add(cat.id)
        for pat in cat.patterns:
            if not pat.regex.match(pat.example):
                report.error("data/catalogues.yaml",
                             f"{cat.id}: example {pat.example!r} does not match its own pattern")
            if pat.frame not in ("icrs", "fk4", "icrs-deg", "galactic", "none"):
                report.error("data/catalogues.yaml", f"{cat.id}: unknown frame {pat.frame!r}")
            groups = set(pat.regex.groupindex)
            need = {"icrs": {"ra", "dec"}, "fk4": {"ra", "dec"}, "icrs-deg": {"ra", "dec"},
                    "galactic": {"l", "b"}, "none": set()}.get(pat.frame, set())
            if not need <= groups:
                report.error("data/catalogues.yaml",
                             f"{cat.id}: pattern for frame {pat.frame} needs groups {sorted(need)}")
        examples = [p.example for p in cat.patterns]
        for ex in examples:
            matches = [c.id for c in db.catalogues for p in c.patterns if p.regex.match(ex)]
            if len(set(matches)) > 1:
                report.error("data/catalogues.yaml",
                             f"example {ex!r} matches several catalogues: {sorted(set(matches))}")


def group_by_catalogue(db: Database):
    """{catalogue id: [(designation, cluster slug)]} for the catalogue index."""
    out = defaultdict(list)
    for c in db.clusters:
        for n in [c["name"]] + list(c.get("aka", [])) + list(c.get("designations", [])):
            hits = identify(n, db.catalogues)
            if hits:
                out[hits[0].catalogue.id].append((n, c["_slug"]))
    return out
