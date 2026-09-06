#!/usr/bin/env python3
"""Shared reader for context-library documents.

Both validate.py and build_manifest.py parse the same files, so the frontmatter
split, the YAML load and the heading scan live here.

PyYAML is used when it is installed. When it is not, a strict subset parser
handles the shape the template uses and raises on anything it does not
recognise, rather than guessing at a value the caller would then trust.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

HAVE_PYYAML = _yaml is not None

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories holding documents. Everything else in the repo is scaffolding.
DOC_ROOTS: Tuple[str, ...] = ("context", "skills")

# A leading underscore marks a file as a template: it is checked for structure
# so it cannot drift away from what the validator wants, but it is not indexed.
TEMPLATE_PREFIX = "_"

VALIDATION_STATUSES: Tuple[str, ...] = ("unvalidated", "piloted", "proven")

REQUIRED_FIELDS: Tuple[str, ...] = (
    "name",
    "type",
    "description",
    "validation_status",
    "last_validated",
)

KNOWN_FIELDS: Tuple[str, ...] = REQUIRED_FIELDS + ("sources",)

# Matched against the part of an H2 before any em dash subtitle.
REQUIRED_SECTIONS: Tuple[str, ...] = (
    "Why this document exists",
    "Gotchas",
    "Conventions",
    "Off-limits",
    "Definition of done",
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(?P<body>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

# Splits `Gotchas — things that have actually broken` down to `Gotchas`.
_SUBTITLE_RE = re.compile(r"\s+(?:—|–|--|:)\s+.*$")

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class FrontmatterError(Exception):
    """Raised when frontmatter is missing or cannot be parsed."""


@dataclass
class Document:
    """A parsed markdown document with its frontmatter and heading structure."""

    path: Path
    rel_path: str
    collection: str
    is_template: bool
    raw_frontmatter: str
    frontmatter_start_line: int
    body: str
    body_start_line: int
    meta: Dict[str, Any] = field(default_factory=dict)
    headings: List[Tuple[int, int, str]] = field(default_factory=list)
    parse_error: Optional[str] = None

    @property
    def stem(self) -> str:
        return self.path.stem

    def get(self, key: str, default: Any = None) -> Any:
        return self.meta.get(key, default)

    def frontmatter_line(self, key: str) -> int:
        """Line number of a frontmatter key, for error messages."""
        pattern = re.compile(r"^%s\s*:" % re.escape(key))
        for offset, line in enumerate(self.raw_frontmatter.splitlines()):
            if pattern.match(line):
                return self.frontmatter_start_line + offset
        return self.frontmatter_start_line


def normalize_value(value: Any) -> Any:
    """Make loaded YAML JSON-safe and parser-independent.

    PyYAML turns `2026-08-27` into a date object while the fallback parser
    leaves it a string. Everything downstream wants the ISO string.
    """
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): normalize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_value(v) for v in value]
    return value


def split_frontmatter(text: str) -> Tuple[str, str, int]:
    """Return (raw frontmatter, body, 1-based line number where body starts)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise FrontmatterError(
            "no YAML frontmatter found: the file must open with a --- line, "
            "the fields, then a closing --- line"
        )
    raw = match.group("body")
    body = text[match.end():]
    body_start_line = text.count("\n", 0, match.end()) + 1
    return raw, body, body_start_line


def load_frontmatter(raw: str) -> Dict[str, Any]:
    """Parse frontmatter into a dict, via PyYAML when available."""
    if HAVE_PYYAML:
        try:
            loaded = _yaml.safe_load(raw)
        except _yaml.YAMLError as exc:
            raise FrontmatterError("invalid YAML: %s" % _one_line(str(exc)))
    else:
        loaded = _parse_yaml_subset(raw)

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise FrontmatterError(
            "frontmatter must be a mapping of fields, got %s" % type(loaded).__name__
        )
    return {str(k): normalize_value(v) for k, v in loaded.items()}


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _parse_yaml_subset(raw: str) -> Dict[str, Any]:
    """Parse the flat `key: value` / `key:` + `- item` subset the template uses.

    Deliberately narrow. Anything richer raises and points at PyYAML instead of
    being silently mis-read.
    """
    result: Dict[str, Any] = {}
    current_key: Optional[str] = None
    lines = raw.splitlines()

    for number, line in enumerate(lines, start=1):
        if "\t" in line:
            raise _subset_error(number, "tab indentation is not valid YAML")
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        item_match = re.match(r"^\s+-\s*(?P<value>.*)$", line)
        if item_match:
            if current_key is None:
                raise _subset_error(number, "list item before any field name")
            existing = result.get(current_key)
            if not isinstance(existing, list):
                existing = []
                result[current_key] = existing
            existing.append(_scalar(item_match.group("value"), number))
            continue

        if line[:1].isspace():
            raise _subset_error(
                number, "indented mappings are not supported without PyYAML"
            )

        key_match = re.match(
            r"^(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)\s*:(?:\s(?P<value>.*))?$", line
        )
        if not key_match:
            raise _subset_error(number, "expected `field: value`, got %r" % line)

        key = key_match.group("key")
        if key in result:
            raise _subset_error(number, "duplicate field %r" % key)

        raw_value = (key_match.group("value") or "").strip()
        current_key = key
        result[key] = None if raw_value == "" else _scalar(raw_value, number)

    return result


def _subset_error(line_number: int, message: str) -> FrontmatterError:
    suffix = "" if HAVE_PYYAML else " (install PyYAML for full YAML support)"
    return FrontmatterError("frontmatter line %d: %s%s" % (line_number, message, suffix))


def _scalar(text: str, line_number: int) -> Any:
    text = text.strip()
    if not text:
        return None

    if text[0] in "{[" and text not in ("[]", "{}"):
        raise _subset_error(line_number, "inline collections are not supported")
    if text in ("[]",):
        return []
    if text in ("{}",):
        return {}
    if text[0] in "|>&*":
        raise _subset_error(
            line_number, "block scalars and anchors are not supported"
        )

    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        inner = text[1:-1]
        if text[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")

    text = _strip_trailing_comment(text)

    lowered = text.lower()
    if lowered in ("null", "~"):
        return None
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if re.match(r"^-?\d+$", text):
        return int(text)
    if re.match(r"^-?\d+\.\d+$", text):
        return float(text)
    return text


def _strip_trailing_comment(text: str) -> str:
    """Drop a ` # comment` tail, the way a YAML plain scalar does."""
    index = _plain_comment_index(text)
    return text[:index].rstrip() if index is not None else text


def _plain_comment_index(text: str) -> Optional[int]:
    """Index where a plain scalar would be cut short by an unquoted `#`."""
    for position, char in enumerate(text):
        if char == "#" and position > 0 and text[position - 1] in " \t":
            return position
    return None


def plain_scalar_comment_risk(raw_frontmatter: str) -> List[Tuple[int, str]]:
    """Find unquoted frontmatter values that YAML will truncate at a ` #`.

    A plain scalar ends at whitespace followed by `#`, so a value that mentions
    an issue number loses everything from the `#` onward without complaint.

    Returns (line number, the text YAML will drop).
    """
    hits: List[Tuple[int, str]] = []
    for number, line in enumerate(raw_frontmatter.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        match = re.match(r"^(?:\s*-\s*|[A-Za-z_][A-Za-z0-9_.\-]*\s*:\s)(?P<value>.+)$", line)
        if not match:
            continue
        value = match.group("value").strip()
        if not value or (len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'"):
            continue
        index = _plain_comment_index(value)
        if index is not None:
            hits.append((number, value[index:]))
    return hits


def extract_headings(body: str, line_offset: int = 0) -> List[Tuple[int, int, str]]:
    """Return (level, line number, text) for ATX headings outside code fences."""
    headings: List[Tuple[int, int, str]] = []
    in_fence = False
    for index, line in enumerate(body.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            headings.append(
                (len(match.group("hashes")), line_offset + index + 1, match.group("text"))
            )
    return headings


def section_key(heading_text: str) -> str:
    """Normalise a heading for comparison against REQUIRED_SECTIONS."""
    text = _SUBTITLE_RE.sub("", heading_text.strip())
    return " ".join(text.lower().replace("_", "-").split())


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return slug.strip("-")


def strip_comments_and_code(body: str) -> str:
    """Body text with HTML comments and fenced code removed, for empty checks."""
    text = _HTML_COMMENT_RE.sub("", body)
    kept: List[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            kept.append(line)
    return "\n".join(kept)


def section_bodies(document: "Document") -> List[Tuple[str, str]]:
    """Return (heading text, prose under it) for each H2, comments removed."""
    lines = document.body.splitlines()
    h2s = [h for h in document.headings if h[0] == 2]
    results: List[Tuple[str, str]] = []
    for position, (_, line_number, text) in enumerate(h2s):
        start = line_number - document.body_start_line + 1
        if position + 1 < len(h2s):
            end = h2s[position + 1][1] - document.body_start_line
        else:
            end = len(lines)
        chunk = "\n".join(lines[start:end])
        results.append((text, strip_comments_and_code(chunk).strip()))
    return results


def read_document(path: Path, repo_root: Path = REPO_ROOT) -> Document:
    """Read and parse one markdown document. Parse failures are recorded, not raised."""
    resolved = Path(path).resolve()
    try:
        rel_path = resolved.relative_to(repo_root).as_posix()
    except ValueError:
        rel_path = resolved.as_posix()

    collection = rel_path.split("/", 1)[0] if "/" in rel_path else ""
    is_template = resolved.name.startswith(TEMPLATE_PREFIX)
    text = resolved.read_text(encoding="utf-8")

    try:
        raw, body, body_start_line = split_frontmatter(text)
    except FrontmatterError as exc:
        return Document(
            path=resolved,
            rel_path=rel_path,
            collection=collection,
            is_template=is_template,
            raw_frontmatter="",
            frontmatter_start_line=1,
            body=text,
            body_start_line=1,
            headings=extract_headings(text),
            parse_error=str(exc),
        )

    document = Document(
        path=resolved,
        rel_path=rel_path,
        collection=collection,
        is_template=is_template,
        raw_frontmatter=raw,
        frontmatter_start_line=2,
        body=body,
        body_start_line=body_start_line,
        headings=extract_headings(body, line_offset=body_start_line - 1),
    )

    try:
        document.meta = load_frontmatter(raw)
    except FrontmatterError as exc:
        document.parse_error = str(exc)
    return document


def iter_doc_paths(
    repo_root: Path = REPO_ROOT, roots: Sequence[str] = DOC_ROOTS
) -> List[Path]:
    """Every .md file under the document roots, in stable order."""
    paths: List[Path] = []
    for root in roots:
        directory = repo_root / root
        if directory.is_dir():
            paths.extend(p for p in directory.rglob("*.md") if p.is_file())
    return sorted(paths, key=lambda p: p.as_posix())


def load_documents(
    repo_root: Path = REPO_ROOT, roots: Sequence[str] = DOC_ROOTS
) -> List[Document]:
    return [read_document(path, repo_root) for path in iter_doc_paths(repo_root, roots)]
