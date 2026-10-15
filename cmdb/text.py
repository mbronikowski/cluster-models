"""Character rules: strict ASCII for identifiers, no look-alike punctuation anywhere.

Names, designations, coordinates, IDs, references and URLs must be plain
printable ASCII. Free prose (notes, credits, model titles) may contain
accented letters and other symbols, but never characters that look like ASCII
punctuation (Unicode hyphens/dashes/minus signs, curly quotes, non-breaking or
zero-width spaces, ...), because those silently break copy-paste and scripts.
"""

from __future__ import annotations

import re
import unicodedata

# Look-alike characters and their ASCII replacements. Used by the migration
# and by `tools/fix_characters.py`; the validator rejects all of them.
LOOKALIKES = {
    # hyphens, dashes and minus signs
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", "−": "-", "⁃": "-", "˗": "-", "﹘": "-",
    "﹣": "-", "－": "-", "➖": "-", "­": "",
    # plus signs
    "＋": "+", "➕": "+", "⁺": "+", "₊": "+",
    # quotes and primes
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "ʼ": "'", "ʹ": "'", "´": "'", "＇": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "ʺ": '"', "＂": '"',
    # dots, colons, commas, slashes
    "…": "...", "․": ".", "．": ".", "∶": ":", "：": ":",
    "，": ",", "⁄": "/", "∕": "/", "／": "/",
    # spaces
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ", "　": " ",
    # zero-width and other invisible format characters
    "​": "", "‌": "", "‍": "", "⁠": "", "﻿": "",
    "‎": "", "‏": "",
}

# Non-ASCII punctuation that is allowed in prose (does not resemble ASCII).
_PROSE_PUNCT_OK = set("§¶·«»¡¿")


def clean_lookalikes(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Replace look-alike characters; return new text and the replacements made."""
    changes = []
    out = []
    for ch in text:
        rep = LOOKALIKES.get(ch)
        if rep is None:
            out.append(ch)
        else:
            out.append(rep)
            changes.append((ch, rep))
    return "".join(out), changes


def char_name(ch: str) -> str:
    return f"U+{ord(ch):04X} {unicodedata.name(ch, 'UNKNOWN')}"


def strict_ascii_problems(value: str) -> list[str]:
    """Problems for identifier-like strings (names, IDs, coordinates, URLs)."""
    problems = []
    bad = sorted({ch for ch in value if not (" " <= ch <= "~")})
    for ch in bad:
        hint = LOOKALIKES.get(ch)
        extra = f" (looks like {hint!r})" if hint else ""
        problems.append(f"non-ASCII character {char_name(ch)}{extra}")
    if value != value.strip():
        problems.append("leading or trailing whitespace")
    if "  " in value:
        problems.append("double space")
    return problems


def prose_problems(value: str) -> list[str]:
    """Problems for free text: accented letters fine, look-alike punctuation not."""
    problems = []
    seen = set()
    for ch in value:
        if ch in seen or ch == "\n" or " " <= ch <= "~":
            continue
        seen.add(ch)
        cat = unicodedata.category(ch)
        if ch in LOOKALIKES:
            problems.append(
                f"look-alike character {char_name(ch)} (use {LOOKALIKES[ch]!r} instead)"
            )
        elif cat[0] in "Z" or cat[0] == "C":
            problems.append(f"invisible/control character {char_name(ch)}")
        elif cat[0] == "P" and ch not in _PROSE_PUNCT_OK:
            problems.append(f"non-ASCII punctuation {char_name(ch)}")
        elif 0xFF00 <= ord(ch) <= 0xFFEF:
            problems.append(f"full-width character {char_name(ch)}")
    if "\t" in value:
        problems.append("tab character")
    return problems


_SLUG_KEEP = re.compile(r"[a-z0-9.]")


def slugify(name: str) -> str:
    """URL/file slug: '+' -> 'p', coordinate minus -> 'm', other separators -> '-'.

    A hyphen is treated as a minus sign when it is followed by a digit and
    preceded by a digit or '.', e.g. 'MACS J0416.1-2403' -> 'macs-j0416.1m2403'
    while 'SPT-CL J0615-5746' -> 'spt-cl-j0615m5746'.
    """
    out = []
    n = len(name)
    for i, ch in enumerate(name):
        prev = name[i - 1] if i > 0 else ""
        nxt = name[i + 1] if i + 1 < n else ""
        if ch == "+":
            out.append("p")
        elif ch == "-" and nxt.isdigit() and (prev.isdigit() or prev == "."):
            out.append("m")
        elif _SLUG_KEEP.match(ch.lower()):
            out.append(ch.lower())
        else:
            out.append("-")
    slug = re.sub(r"-+", "-", "".join(out)).strip("-.")
    return slug


def ascii_fold(text: str) -> str:
    """'Rihtaršič' -> 'Rihtarsic' (drop accents; other non-ASCII removed)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if ord(ch) < 128)


def anchor_id(title: str) -> str:
    """GitHub-style heading anchor, ASCII-folded ('Rihtaršič et al. (2026)' ->
    'rihtarsic-et-al-2026'). Old wiki '#section' links map onto these."""
    s = ascii_fold(title).strip().lower()
    s = re.sub(r"[^a-z0-9\- ]", "", s)
    s = re.sub(r"\s+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")
