"""Coordinate parsing/formatting and the few frame conversions the checks need.

Kept dependency-free on purpose (no astropy): accuracy of ~1 arcsec is far
better than the arcminute tolerances used when checking designations.
"""

from __future__ import annotations

import math
import re

RA_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)$")
DEC_RE = re.compile(r"^([+-])(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)$")


def parse_ra(text: str) -> float:
    """'hh:mm:ss.s' -> degrees. Raises ValueError on bad format/range."""
    m = RA_RE.match(text)
    if not m:
        raise ValueError(f"RA {text!r} is not in 'hh:mm:ss.s' format")
    h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    if h > 23 or mnt > 59 or s >= 60:
        raise ValueError(f"RA {text!r} out of range")
    return 15.0 * (h + mnt / 60 + s / 3600)


def parse_dec(text: str) -> float:
    """'+dd:mm:ss.s' -> degrees. The sign is mandatory."""
    m = DEC_RE.match(text)
    if not m:
        raise ValueError(
            f"Dec {text!r} is not in '+dd:mm:ss.s' format (explicit sign required)"
        )
    sign = -1.0 if m.group(1) == "-" else 1.0
    d, mnt, s = int(m.group(2)), int(m.group(3)), float(m.group(4))
    if d > 90 or mnt > 59 or s >= 60 or (d == 90 and (mnt or s)):
        raise ValueError(f"Dec {text!r} out of range")
    return sign * (d + mnt / 60 + s / 3600)


def format_ra(deg: float, decimals: int = 2) -> str:
    total = (deg % 360.0) / 15.0 * 3600.0
    total = round(total, decimals)
    h = int(total // 3600)
    m = int((total - h * 3600) // 60)
    s = total - h * 3600 - m * 60
    if h == 24:
        h = 0
    width = 3 + decimals if decimals else 2
    return f"{h:02d}:{m:02d}:{s:0{width}.{decimals}f}"


def format_dec(deg: float, decimals: int = 1) -> str:
    sign = "-" if deg < 0 else "+"
    total = round(abs(deg) * 3600.0, decimals)
    d = int(total // 3600)
    m = int((total - d * 3600) // 60)
    s = total - d * 3600 - m * 60
    width = 3 + decimals if decimals else 2
    return f"{sign}{d:02d}:{m:02d}:{s:0{width}.{decimals}f}"


def parse_free(text: str) -> tuple[float, float] | None:
    """Parse a free-form position: sexagesimal (':' or ' ' or hms/dms letters)
    or decimal degrees. Returns (ra_deg, dec_deg) or None."""
    t = text.strip().replace(",", " ")
    for k, v in {"−": "-", "–": "-", "‐": "-"}.items():
        t = t.replace(k, v)
    t = re.sub(r"[hdms:°'\"]", " ", t)
    parts = t.split()
    try:
        if len(parts) == 2:
            ra, dec = float(parts[0]), float(parts[1])
            if not (0 <= ra < 360 and -90 <= dec <= 90):
                return None
            return ra, dec
        if len(parts) == 6:
            h, mnt, s = (float(x) for x in parts[:3])
            sign = -1.0 if parts[3].startswith("-") else 1.0
            d = abs(float(parts[3]))
            dm, ds = float(parts[4]), float(parts[5])
            return 15 * (h + mnt / 60 + s / 3600), sign * (d + dm / 60 + ds / 3600)
    except ValueError:
        return None
    return None


def separation(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Angular separation in degrees (Vincenty formula)."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    dra = r2 - r1
    num = math.hypot(
        math.cos(d2) * math.sin(dra),
        math.cos(d1) * math.sin(d2) - math.sin(d1) * math.cos(d2) * math.cos(dra),
    )
    den = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(dra)
    return math.degrees(math.atan2(num, den))


# --- frame conversions -------------------------------------------------------

# ICRS/J2000 equatorial -> Galactic (Hipparcos definition).
_GAL = (
    (-0.0548755604162154, -0.8734370902348850, -0.4838350155487132),
    (+0.4941094278755837, -0.4448296299600112, +0.7469822444972189),
    (-0.8676661490190047, -0.1980763734312015, +0.4559837761750669),
)


def _vec(ra: float, dec: float):
    r, d = math.radians(ra), math.radians(dec)
    return (math.cos(d) * math.cos(r), math.cos(d) * math.sin(r), math.sin(d))


def _sph(v):
    x, y, z = v
    lon = math.degrees(math.atan2(y, x)) % 360.0
    lat = math.degrees(math.atan2(z, math.hypot(x, y)))
    return lon, lat


def _mul(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def _transpose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def icrs_to_galactic(ra: float, dec: float) -> tuple[float, float]:
    return _sph(_mul(_GAL, _vec(ra, dec)))


def galactic_to_icrs(lon: float, lat: float) -> tuple[float, float]:
    return _sph(_mul(_transpose(_GAL), _vec(lon, lat)))


def _precession_matrix_j2000_to(t_centuries: float):
    """IAU 1976 precession from J2000 to epoch J2000 + t (Julian centuries)."""
    t = t_centuries
    asec = math.pi / 180 / 3600
    zeta = (2306.2181 * t + 0.30188 * t**2 + 0.017998 * t**3) * asec
    z = (2306.2181 * t + 1.09468 * t**2 + 0.018203 * t**3) * asec
    theta = (2004.3109 * t - 0.42665 * t**2 - 0.041833 * t**3) * asec
    cz, sz = math.cos(zeta), math.sin(zeta)
    cZ, sZ = math.cos(z), math.sin(z)
    ct, st = math.cos(theta), math.sin(theta)
    return (
        (cZ * ct * cz - sZ * sz, -cZ * ct * sz - sZ * cz, -cZ * st),
        (sZ * ct * cz + cZ * sz, -sZ * ct * sz + cZ * cz, -sZ * st),
        (st * cz, -st * sz, ct),
    )


# B1950.0 = JD 2433282.4235; J2000.0 = JD 2451545.0
_T_B1950 = (2433282.4235 - 2451545.0) / 36525.0
_P_TO_B1950 = _precession_matrix_j2000_to(_T_B1950)


def icrs_to_b1950(ra: float, dec: float) -> tuple[float, float]:
    """Approximate FK4 B1950 position (precession only, no E-terms: <1 arcsec)."""
    return _sph(_mul(_P_TO_B1950, _vec(ra, dec)))


def b1950_to_icrs(ra: float, dec: float) -> tuple[float, float]:
    return _sph(_mul(_transpose(_P_TO_B1950), _vec(ra, dec)))
