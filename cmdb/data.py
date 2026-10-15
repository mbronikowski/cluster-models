"""Load the data directory into plain Python structures (shared by validate/build)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import DATA, yamlio
from .catalogues import Catalogue, load_registry


@dataclass
class Database:
    root: Path
    clusters: list[dict] = field(default_factory=list)      # each has '_file', '_slug'
    transients: list[dict] = field(default_factory=list)    # each has '_file', '_slug'
    programs: list[dict] = field(default_factory=list)
    references: dict = field(default_factory=dict)
    vocabulary: dict = field(default_factory=dict)
    catalogues: list[Catalogue] = field(default_factory=list)
    load_errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def cluster_by_slug(self) -> dict:
        return {c["_slug"]: c for c in self.clusters}

    @property
    def program_by_id(self) -> dict:
        return {p["id"]: p for p in self.programs if isinstance(p, dict) and "id" in p}


def _load(path: Path, db: Database):
    try:
        return yamlio.load(path)
    except Exception as exc:  # noqa: BLE001 - report any parse problem
        db.load_errors.append((str(path.relative_to(db.root.parent)), f"cannot parse YAML: {exc}"))
        return None


def load_database(data_dir: Path | None = None) -> Database:
    data_dir = Path(data_dir or DATA)
    db = Database(root=data_dir)
    for path in sorted((data_dir / "clusters").glob("*")):
        if path.suffix != ".yaml":
            db.load_errors.append((str(path.relative_to(data_dir.parent)),
                                   "unexpected file (cluster files must end in .yaml)"))
            continue
        rec = _load(path, db)
        if rec is None:
            continue
        if not isinstance(rec, dict):
            db.load_errors.append((str(path.relative_to(data_dir.parent)), "file is not a mapping"))
            continue
        rec["_file"] = str(path.relative_to(data_dir.parent))
        rec["_slug"] = path.stem
        db.clusters.append(rec)
    for path in sorted((data_dir / "transients").glob("*.yaml")):
        rec = _load(path, db)
        if isinstance(rec, dict):
            rec["_file"] = str(path.relative_to(data_dir.parent))
            rec["_slug"] = path.stem
            db.transients.append(rec)
    db.programs = _load(data_dir / "programs.yaml", db) or []
    db.references = _load(data_dir / "references.yaml", db) or {}
    db.vocabulary = _load(data_dir / "vocabulary.yaml", db) or {}
    try:
        db.catalogues = load_registry(data_dir / "catalogues.yaml")
    except Exception as exc:  # noqa: BLE001
        db.load_errors.append(("data/catalogues.yaml", f"cannot load registry: {exc}"))
    return db


def strip_private(rec):
    """Copy of a record without the loader's '_file'/'_slug' keys."""
    if isinstance(rec, dict):
        return {k: strip_private(v) for k, v in rec.items() if not k.startswith("_")}
    if isinstance(rec, list):
        return [strip_private(v) for v in rec]
    return rec
