"""Catalogue registry: identify designations, decode positions, build search keys."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from . import DATA
from .coords import icrs_to_b1950, icrs_to_galactic

TYPE_LABELS = {
    "sz": "SZ surveys",
    "xray": "X-ray surveys",
    "optical": "Optical/IR surveys",
    "lens": "Lens-system names",
    "source": "X-ray source designations",
    "galaxy": "Galaxy (BCG) designations",
    "other": "Other designations",
}


@dataclass
class Pattern:
    regex: re.Pattern
    frame: str
    example: str
    type: str
    tolerance: float


@dataclass
class Catalogue:
    id: str
    label: str
    name: str
    type: str
    tolerance: float
    ref: str = ""
    patterns: list[Pattern] = field(default_factory=list)


@dataclass
class Identified:
    catalogue: Catalogue
    pattern: Pattern
    match: re.Match

    @property
    def type(self) -> str:
        return self.pattern.type


def load_registry(path=None) -> list[Catalogue]:
    raw = yaml.safe_load(open(path or DATA / "catalogues.yaml", encoding="utf-8"))
    cats = []
    for c in raw:
        cat = Catalogue(
            id=c["id"], label=c["label"], name=c["name"], type=c["type"],
            tolerance=float(c["tolerance"]), ref=c.get("ref", ""),
        )
        for p in c["patterns"]:
            cat.patterns.append(Pattern(
                regex=re.compile(p["regex"]), frame=p["frame"], example=p["example"],
                type=p.get("type", cat.type), tolerance=float(p.get("tolerance", cat.tolerance)),
            ))
        cats.append(cat)
    return cats


@lru_cache(maxsize=1)
def registry() -> tuple[Catalogue, ...]:
    return tuple(load_registry())


def identify(name: str, cats=None) -> list[Identified]:
    """All (catalogue, pattern) pairs matching a designation (should be exactly one)."""
    hits = []
    for cat in cats or registry():
        for pat in cat.patterns:
            m = pat.regex.match(name)
            if m:
                hits.append(Identified(cat, pat, m))
    return hits


# --- decoding positions encoded in designations ------------------------------

def _split(num: str) -> tuple[str, str]:
    sign = ""
    if num[:1] in "+-":
        sign, num = num[0], num[1:]
    whole, _, frac = num.partition(".")
    return sign + whole, frac


def _decode_ra_digits(text: str) -> tuple[float, float]:
    """Sexagesimal RA digits -> (degrees, unit in degrees)."""
    whole, frac = _split(text)
    fr = float("0." + frac) if frac else 0.0
    fstep = 10.0 ** -len(frac) if frac else 1.0
    n = len(whole)
    if n == 4:      # HHMM(.m)
        h, m = int(whole[:2]), int(whole[2:]) + fr
        return 15 * (h + m / 60), 15 * fstep / 60
    if n == 5:      # HHMMm
        h, m = int(whole[:2]), int(whole[2:4]) + int(whole[4]) / 10
        return 15 * (h + m / 60), 15 * 0.1 / 60
    if n == 6:      # HHMMSS(.s)
        h, m, s = int(whole[:2]), int(whole[2:4]), int(whole[4:]) + fr
        return 15 * (h + m / 60 + s / 3600), 15 * fstep / 3600
    if n == 8:      # HHMMSSss (2MASS)
        h, m = int(whole[:2]), int(whole[2:4])
        s = int(whole[4:6]) + int(whole[6:]) / 100
        return 15 * (h + m / 60 + s / 3600), 15 * 0.01 / 3600
    raise ValueError(f"cannot decode RA digits {text!r}")


def _decode_dec_digits(text: str) -> tuple[float, float]:
    whole, frac = _split(text)
    sign = -1.0 if whole.startswith("-") else 1.0
    digits = whole.lstrip("+-")
    fr = float("0." + frac) if frac else 0.0
    fstep = 10.0 ** -len(frac) if frac else 1.0
    n = len(digits)
    if n == 2:      # DD(.d)
        return sign * (int(digits) + fr), fstep
    if n == 3:      # DDd
        return sign * (int(digits[:2]) + int(digits[2]) / 10), 0.1
    if n == 4:      # DDMM(.m)
        return sign * (int(digits[:2]) + (int(digits[2:]) + fr) / 60), fstep / 60
    if n == 6:      # DDMMSS(.s)
        return (sign * (int(digits[:2]) + int(digits[2:4]) / 60 + (int(digits[4:]) + fr) / 3600),
                fstep / 3600)
    if n == 7:      # DDMMSSs (2MASS)
        s = int(digits[4:6]) + int(digits[6]) / 10
        return sign * (int(digits[:2]) + int(digits[2:4]) / 60 + s / 3600), 0.1 / 3600
    raise ValueError(f"cannot decode Dec digits {text!r}")


def _decimal(text: str) -> tuple[float, float]:
    _, frac = _split(text)
    return float(text), 10.0 ** -len(frac) if frac else 1.0


def encoded_position(ident: Identified):
    """Return (frame, lon, lat, unit_lon, unit_lat) or None if nothing encoded."""
    frame = ident.pattern.frame
    gd = ident.match.groupdict()
    if frame == "none":
        return None
    if frame in ("icrs", "fk4"):
        ra, ura = _decode_ra_digits(gd["ra"])
        dec, udec = _decode_dec_digits(gd["dec"])
        return frame, ra, dec, ura, udec
    if frame == "icrs-deg":
        ra, ura = _decimal(gd["ra"])
        dec, udec = _decimal(gd["dec"])
        return frame, ra, dec, ura, udec
    if frame == "galactic":
        lon, ul = _decimal(gd["l"])
        lat, ub = _decimal(gd["b"])
        return frame, lon, lat, ul, ub
    raise ValueError(f"unknown frame {frame}")


def position_excess(ident: Identified, ra: float, dec: float):
    """Arcmin by which (ra, dec) [ICRS deg] lies outside the box encoded by the
    designation (box = +/- one unit of the last digit, i.e. truncation or
    rounding). Returns None if the designation encodes no position."""
    enc = encoded_position(ident)
    if enc is None:
        return None
    frame, lon0, lat0, ulon, ulat = enc
    if frame == "fk4":
        lon, lat = icrs_to_b1950(ra, dec)
    elif frame == "galactic":
        lon, lat = icrs_to_galactic(ra, dec)
    else:
        lon, lat = ra, dec
    dlon = (lon - lon0 + 180.0) % 360.0 - 180.0
    # box spans [v - unit, v + unit] in each coordinate
    ex_lon = max(0.0, abs(dlon) - ulon) * math.cos(math.radians(lat))
    ex_lat = max(0.0, abs(lat - lat0) - ulat)
    return math.hypot(ex_lon, ex_lat) * 60.0


# --- search keys ---------------------------------------------------------------

_LETTER_DASH = re.compile(r"(?<=[A-Z])-(?=[A-Z])")
_PREFIX_J = re.compile(r"^([A-Z][A-Z0-9]*?[A-Z])J(?=\d)")
_ABELL = re.compile(r"^(?:ABELL|ACO)(?=S?\d)")
_A_ZEROS = re.compile(r"^(AS?)0+(?=\d)")


def search_key(text: str) -> str:
    """Normalise a name or query for substring matching. Mirrors normKey() in
    static/search.js -- keep the two in sync."""
    s = text.upper()
    for k, v in (("−", "-"), ("–", "-"), ("‐", "-"), ("‑", "-")):
        s = s.replace(k, v)
    s = re.sub(r"[\s_]+", "", s)
    s = _LETTER_DASH.sub("", s)
    s = _PREFIX_J.sub(r"\1", s)
    s = _ABELL.sub("A", s)
    s = _A_ZEROS.sub(r"\1", s)
    return s


def search_keys(name: str) -> list[str]:
    """Search keys for one name, including common short forms (M0416, SPT0615)."""
    keys = [search_key(name)]
    k = keys[0]
    for long, short in (("MACS", "M"), ("SPTCL", "SPT"), ("ACTCL", "ACT"), ("RXC", "RX")):
        if k.startswith(long) and k[len(long):len(long) + 1].isdigit():
            keys.append(short + k[len(long):])
    return list(dict.fromkeys(keys))
