"""Read/write data files in a fixed, readable house style.

`tools/format_data.py` rewrites every file through `dump_cluster` etc., so the
layout stays consistent no matter who edited a file.
"""

from __future__ import annotations

import re

import yaml

WRAP = 92


class _Loader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate keys (a common hand-editing mistake)."""


def _construct_mapping(loader, node, deep=False):
    keys = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in keys:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark)
        keys.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_Loader)


def scalar(value) -> str:
    """One-line YAML representation of a scalar (quoted only when needed)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = yaml.safe_dump(value, default_flow_style=True, width=10_000, allow_unicode=True)
    text = text.strip()
    if text.endswith("\n..."):
        text = text[:-4].strip()
    if text.endswith("..."):
        text = text[:-3].strip()
    if "\n" in text:
        raise ValueError(f"multi-line scalar where one line expected: {value!r}")
    return text


def _flow_list(items) -> str:
    return "[" + ", ".join(scalar(x) for x in items) + "]"


def _fits_flow(items, indent: int, key: str) -> bool:
    if not items:
        return True
    rendered = _flow_list(items)
    if any("," in str(x) or "[" in str(x) or "]" in str(x) for x in items):
        return False
    return indent + len(key) + 2 + len(rendered) <= WRAP


# a Markdown link, with any punctuation glued to it, is one token and never split
_TOKEN = re.compile(r"\S*\[[^\]]*\]\([^)\s]*\)\S*|\S+")


def _wrap(line: str, width: int) -> list[str]:
    """Greedy wrap that never splits a Markdown link '[text](url)'."""
    out, cur = [], ""
    for tok in _TOKEN.findall(line):
        # never start a continuation line with something Markdown would read as a
        # list item, heading or quote ('- x', '1. x', '# x', '> x')
        risky = re.fullmatch(r"[-+*>]|#{1,6}|\d+[.)]", tok)
        if cur and len(cur) + 1 + len(tok) > width and not risky:
            out.append(cur)
            cur = tok
        else:
            cur = f"{cur} {tok}" if cur else tok
    if cur:
        out.append(cur)
    return out or [""]


def _block_text(text: str, indent: int) -> list[str]:
    """Literal block scalar (|-), long lines wrapped at spaces (Markdown-safe)."""
    pad = " " * indent
    lines = []
    for para_line in text.split("\n"):
        if not para_line.strip():
            lines.append("")
            continue
        lines.extend(_wrap(para_line.strip(), max(40, WRAP - indent)))
    return [(pad + ln) if ln else "" for ln in lines]


ALWAYS_QUOTED = ("ra", "dec")      # sexagesimal strings must never be read as numbers
ALWAYS_BLOCK = ("designations",)   # one designation per line: easier to edit and diff


def emit_value(key: str, value, indent: int, out: list[str], long_text_keys=()):
    pad = " " * indent
    if value is None or value == [] or value == {} or value == "":
        return
    if key in ALWAYS_QUOTED and isinstance(value, str):
        out.append(f'{pad}{key}: "{value}"')
        return
    if isinstance(value, str) and (key in long_text_keys) and (
            "\n" in value or len(value) + indent + len(key) + 2 > WRAP or ": " in value):
        out.append(f"{pad}{key}: |-")
        out.extend(_block_text(value.strip("\n"), indent + 2))
    elif isinstance(value, list):
        if (all(not isinstance(x, (dict, list)) for x in value) and key not in ALWAYS_BLOCK
                and _fits_flow(value, indent, key)):
            out.append(f"{pad}{key}: {_flow_list(value)}")
        else:
            out.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    emit_mapping_item(item, indent + 2, out, long_text_keys)
                else:
                    out.append(f"{pad}  - {scalar(item)}")
    elif isinstance(value, dict):
        out.append(f"{pad}{key}:")
        for k, v in value.items():
            emit_value(k, v, indent + 2, out, long_text_keys)
    else:
        out.append(f"{pad}{key}: {scalar(value)}")


def emit_mapping_item(item: dict, indent: int, out: list[str], long_text_keys=()):
    """A '- key: value' list item with the remaining keys aligned below."""
    first = True
    pad = " " * indent
    for k, v in item.items():
        if v is None or v == [] or v == {} or v == "":
            continue
        sub: list[str] = []
        emit_value(k, v, indent + 2, sub, long_text_keys)
        if first:
            sub[0] = pad + "- " + sub[0][indent + 2:]
            first = False
        out.extend(sub)


CLUSTER_KEYS = [
    "name", "common_names", "aka", "designations", "ra", "dec", "z", "programs",
    "image", "links", "models", "observations", "notes", "ignore_position_check",
]
MODEL_KEYS = [
    "title", "program", "refs", "data", "software", "availability", "status",
    "superseded_by", "tags", "links", "note",
]
TRANSIENT_KEYS = [
    "name", "aliases", "class", "subclass", "status", "images", "cluster", "ra", "dec", "z",
    "discovered", "refs", "links", "notes",
]
LONG_TEXT = ("note", "notes", "credit")


def _ordered(d: dict, keys: list[str]) -> dict:
    extra = [k for k in d if k not in keys]
    if extra:
        raise ValueError(f"unexpected keys {extra}")
    return {k: d[k] for k in keys if k in d}


def dump_cluster(c: dict) -> str:
    c = _ordered(c, CLUSTER_KEYS)
    if "models" in c:
        c["models"] = [_ordered(m, MODEL_KEYS) for m in c["models"]]
    out = ["# One file per cluster. Field reference: docs/data-format.md", ""]
    for key, value in c.items():
        if key in ("image", "models", "notes", "observations") and value:
            out.append("")
        emit_value(key, value, 0, out, LONG_TEXT)
    return "\n".join(out).rstrip() + "\n"


def dump_transient(t: dict) -> str:
    t = _ordered(t, TRANSIENT_KEYS)
    out = ["# Lensed transient / variable source. Field reference: docs/data-format.md", ""]
    for key, value in t.items():
        emit_value(key, value, 0, out, LONG_TEXT)
    return "\n".join(out).rstrip() + "\n"


def dump_list_file(header: str, items: list[dict], keys: list[str]) -> str:
    out = [header.rstrip(), ""]
    for item in items:
        emit_mapping_item(_ordered(item, keys), 0, out, LONG_TEXT)
        out.append("")
    return "\n".join(out).rstrip() + "\n"
