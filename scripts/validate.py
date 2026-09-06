#!/usr/bin/env python3
"""Validate context-library documents and scan the repo for credentials.

Structure checks run over every .md under context/ and skills/:
frontmatter parses, the required fields are present and well formed, the
required sections exist, and `name` matches the filename.

The credential scan runs over every text file in the repo, not just the
documents, because a leaked key is worth catching wherever it lands.

    python3 scripts/validate.py
    python3 scripts/validate.py --strict          # warnings fail too
    python3 scripts/validate.py --json
    python3 scripts/validate.py --max-age-days 180

Exit status is 0 when clean, 1 when anything failed.
A line carrying `pragma: allow-secret` is skipped by the credential scan.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import doclib
from doclib import (
    DATE_RE,
    REPO_ROOT,
    REQUIRED_FIELDS,
    REQUIRED_SECTIONS,
    VALIDATION_STATUSES,
    Document,
)

ERROR = "error"
WARNING = "warning"

ALLOW_PRAGMA = "pragma: allow-secret"

# Directories never worth reading, whether or not git knows about them.
SKIP_DIRS = frozenset(
    {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".ruff_cache"}
)

SKIP_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
        ".tar", ".bz2", ".xz", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mov",
        ".so", ".dylib", ".dll", ".pyc", ".bin", ".wasm",
    }
)

MAX_SCAN_BYTES = 2_000_000

# --- credential detection ---------------------------------------------------

# Vendor-prefixed tokens. Rule names avoid the word "key" so the scanner does
# not trip over its own source.
PREFIXED_SECRETS: Sequence = (
    ("anthropic-sk", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}")),
    ("openai-sk", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("stripe-sk", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("aws-access-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google-api", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack-webhook", re.compile(r"hooks\.slack\.com/services/[A-Za-z0-9_/\-]{20,}")),
    ("huggingface", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}")),
    ("json-web-token", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}")),
    ("private-key-block", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
)

# `NAME = value` where a segment of NAME says the value is sensitive.
# The value runs to the next whitespace, so a trailing ` # comment` falls
# outside it while a `#` inside the secret itself is kept.
_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<name>[A-Za-z][A-Za-z0-9_.\-]{1,60})\s*[:=]\s*"
    r"(?P<value>\"[^\"\n]*\"|'[^'\n]*'|[^\s\"'#]\S*)"
)

SENSITIVE_NAME_PARTS = frozenset(
    {
        "KEY", "KEYS", "APIKEY", "SECRET", "SECRETS", "TOKEN", "TOKENS",
        "PASSWORD", "PASSWD", "PWD", "PASSPHRASE", "CREDENTIAL", "CREDENTIALS",
    }
)

# Values that are obviously stand-ins rather than live secrets.
_PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"[\*x\.\-_]+"                     # ****, xxxx, ----
    r"|<[^>]*>"                        # <your-token>
    r"|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?" # $TOKEN / ${TOKEN}
    r"|\{\{[^}]*\}\}"                  # {{ token }}
    r"|%[A-Za-z_][A-Za-z0-9_]*%"       # %TOKEN%
    r"|(?:your|my|some|the)[-_ ].*"
    r"|(?:changeme|redacted|placeholder|example|dummy|sample|todo|tbd|none|null|nil|unset|empty)"
    r")$",
    re.IGNORECASE,
)

# Punctuation that means we are looking at code or prose, not a secret literal.
_CODE_CHARS = frozenset("()[]{}<>`\"';,\\|!?")

_HEX_BLOB_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_TOKEN_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")

# A path, filename or slug segment: `hermes`, `Projects`, `appdev1`, `HANDOFF`.
# Randomness does not look like this, which is what makes it a useful filter.
_WORDISH_RE = re.compile(r"^(?:[A-Za-z][a-z0-9]*|[A-Z][A-Z0-9]*)$")
_MAX_WORDISH_SEGMENT = 20

MIN_ASSIGNED_VALUE_LENGTH = 6
MIN_ALPHABETIC_VALUE_LENGTH = 16
MIN_CANDIDATE_LENGTH = 20
ENTROPY_THRESHOLD = 4.0


@dataclass
class Finding:
    level: str
    path: str
    line: Optional[int]
    rule: str
    message: str


# --- structure checks -------------------------------------------------------


def check_document(document: Document, max_age_days: int = 0) -> List[Finding]:
    findings: List[Finding] = []

    def add(level: str, rule: str, message: str, line: Optional[int] = None) -> None:
        findings.append(Finding(level, document.rel_path, line, rule, message))

    if document.parse_error:
        add(ERROR, "frontmatter", document.parse_error, 1)
        return findings

    _check_fields(document, add, max_age_days)
    _check_sections(document, add)
    return findings


AddFinding = Callable[..., None]


def _check_fields(document: Document, add: AddFinding, max_age_days: int) -> None:
    meta = document.meta

    for field_name in REQUIRED_FIELDS:
        if field_name not in meta:
            add(ERROR, "missing-field", "frontmatter is missing `%s`" % field_name, 1)

    unknown = sorted(set(meta) - set(doclib.KNOWN_FIELDS))
    if unknown:
        add(
            WARNING,
            "unknown-field",
            "frontmatter has unrecognised field(s): %s" % ", ".join(unknown),
            document.frontmatter_line(unknown[0]),
        )

    name = meta.get("name")
    if "name" in meta:
        if not isinstance(name, str) or not name.strip():
            add(ERROR, "name", "`name` must be a non-empty string",
                document.frontmatter_line("name"))
        elif name != document.stem:
            add(
                ERROR,
                "name-filename-mismatch",
                "`name: %s` does not match the filename `%s.md`" % (name, document.stem),
                document.frontmatter_line("name"),
            )

    doc_type = meta.get("type")
    if "type" in meta and (not isinstance(doc_type, str) or not doc_type.strip()):
        add(ERROR, "type", "`type` must be a non-empty string",
            document.frontmatter_line("type"))

    description = meta.get("description")
    if "description" in meta:
        if not isinstance(description, str) or not description.strip():
            add(ERROR, "description", "`description` must be a non-empty string",
                document.frontmatter_line("description"))
        elif not document.is_template and re.search(
            r"\b(replace this|todo|tbd|fill in|lorem ipsum)\b", description, re.IGNORECASE
        ):
            add(
                WARNING,
                "description-placeholder",
                "`description` still reads like template text; an agent picks "
                "documents to load from this line",
                document.frontmatter_line("description"),
            )

    status = meta.get("validation_status")
    if "validation_status" in meta and status not in VALIDATION_STATUSES:
        add(
            ERROR,
            "validation-status",
            "`validation_status: %r` is not one of %s"
            % (status, ", ".join(VALIDATION_STATUSES)),
            document.frontmatter_line("validation_status"),
        )

    _check_last_validated(document, add, status, max_age_days)

    sources = meta.get("sources")
    if sources is not None and not isinstance(sources, list):
        add(ERROR, "sources", "`sources` must be a list when present",
            document.frontmatter_line("sources"))
    elif isinstance(sources, list) and not sources and status in ("piloted", "proven"):
        add(
            WARNING,
            "sources-empty",
            "`validation_status: %s` with no `sources`; record what it was "
            "validated against" % status,
            document.frontmatter_line("sources"),
        )

    for line_number, dropped in doclib.plain_scalar_comment_risk(document.raw_frontmatter):
        add(
            WARNING,
            "yaml-comment-truncation",
            "unquoted value is cut short by ` #` and YAML drops %r; wrap the "
            "value in quotes" % dropped,
            document.frontmatter_start_line + line_number - 1,
        )


def _check_last_validated(
    document: Document, add: AddFinding, status: object, max_age_days: int
) -> None:
    if "last_validated" not in document.meta:
        return

    value = document.meta.get("last_validated")
    line = document.frontmatter_line("last_validated")

    if value is None or (isinstance(value, str) and not value.strip()):
        # An unvalidated document has no honest date to put here.
        if status != "unvalidated":
            add(
                ERROR,
                "last-validated",
                "`last_validated` may only be blank while `validation_status` "
                "is unvalidated",
                line,
            )
        return

    if not isinstance(value, str) or not DATE_RE.match(value):
        add(ERROR, "last-validated", "`last_validated` must be YYYY-MM-DD, got %r" % value, line)
        return

    try:
        validated_on = datetime.date(int(value[0:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        add(ERROR, "last-validated", "`last_validated: %s` is not a real date" % value, line)
        return

    today = datetime.date.today()
    if validated_on > today:
        add(WARNING, "last-validated-future",
            "`last_validated: %s` is in the future" % value, line)
    elif max_age_days > 0 and status in ("piloted", "proven"):
        age = (today - validated_on).days
        if age > max_age_days:
            add(
                WARNING,
                "stale",
                "`%s` was last validated %d days ago (limit %d); re-check it or "
                "drop it back to unvalidated" % (status, age, max_age_days),
                line,
            )


def _check_sections(document: Document, add: AddFinding) -> None:
    h1s = [h for h in document.headings if h[0] == 1]
    if not h1s:
        add(ERROR, "title", "document has no `# ` title", document.body_start_line)
    elif len(h1s) > 1:
        add(WARNING, "title", "document has %d `# ` titles; expected one" % len(h1s), h1s[1][1])

    h2s = [(line, text) for level, line, text in document.headings if level == 2]
    present = {doclib.section_key(text): line for line, text in h2s}
    order = [doclib.section_key(text) for _, text in h2s]

    for required in REQUIRED_SECTIONS:
        if doclib.section_key(required) not in present:
            add(ERROR, "missing-section", "missing required section `## %s`" % required,
                document.body_start_line)

    expected_order = [doclib.section_key(s) for s in REQUIRED_SECTIONS]
    seen = [key for key in order if key in expected_order]
    if seen and seen != [key for key in expected_order if key in seen]:
        add(
            WARNING,
            "section-order",
            "required sections are out of order; expected %s"
            % " -> ".join(REQUIRED_SECTIONS),
            document.body_start_line,
        )

    if not document.is_template:
        for heading, prose in doclib.section_bodies(document):
            if not prose:
                add(WARNING, "empty-section", "section `## %s` has no content" % heading,
                    present.get(doclib.section_key(heading), document.body_start_line))

        name = document.meta.get("name")
        if h1s and isinstance(name, str) and doclib.slugify(h1s[0][2]) != name:
            add(
                WARNING,
                "title-name-mismatch",
                "title %r does not slugify to `name: %s`" % (h1s[0][2], name),
                h1s[0][1],
            )


# --- credential scan --------------------------------------------------------


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _looks_like_name(token: str) -> bool:
    """True for paths and slug-cased names: `infra/openshell/hermes-sandbox/config`.

    Every separated segment has to read like a word or a SCREAMING_CASE name.
    This is what keeps the entropy rule off filenames, which in this repo are
    long enough and varied enough to clear the entropy threshold on their own.
    """
    parts = [p for p in re.split(r"[-_/.]", token) if p]
    if len(parts) < 2:
        return False
    return all(len(p) <= _MAX_WORDISH_SEGMENT and _WORDISH_RE.match(p) for p in parts)


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(value.strip()))


def _looks_like_code(value: str) -> bool:
    """True when an assigned value is a code expression or prose, not a literal."""
    if _CODE_CHARS & set(value):
        return True
    # `os.environ`, `assigned-value`, `Sequence`: letters plus separators only.
    letters_only = re.sub(r"[-_.]", "", value)
    return letters_only.isalpha() and len(value) < MIN_ALPHABETIC_VALUE_LENGTH


def _high_entropy_reason(token: str) -> Optional[str]:
    if _looks_like_name(token):
        return None

    entropy = shannon_entropy(token)
    has_lower = any(c.islower() for c in token)
    has_upper = any(c.isupper() for c in token)
    has_digit = any(c.isdigit() for c in token)

    if len(token) >= MIN_CANDIDATE_LENGTH and has_lower and has_upper and has_digit:
        if entropy >= ENTROPY_THRESHOLD:
            return "mixed-case alphanumeric, entropy %.2f" % entropy
    if len(token) >= 32 and not has_lower and (has_upper and has_digit):
        if entropy >= ENTROPY_THRESHOLD:
            return "uppercase alphanumeric, entropy %.2f" % entropy
    if len(token) >= 32 and any(c in "+/=" for c in token):
        if entropy >= ENTROPY_THRESHOLD:
            return "base64-shaped, entropy %.2f" % entropy
    return None


def scan_text_for_secrets(text: str, rel_path: str) -> List[Finding]:
    findings: List[Finding] = []

    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_PRAGMA in line:
            continue

        for rule, pattern in PREFIXED_SECRETS:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(ERROR, rel_path, number, "secret:" + rule,
                            "looks like a credential (%s): %s"
                            % (rule, _redact(match.group(0))))
                )

        for match in _ASSIGNMENT_RE.finditer(line):
            name = match.group("name")
            parts = [p.upper() for p in re.split(r"[_.\-]", name) if p]
            if not any(p in SENSITIVE_NAME_PARTS for p in parts):
                continue

            value = match.group("value").strip("\"'").strip()
            if len(value) < MIN_ASSIGNED_VALUE_LENGTH:
                continue
            if value.isdigit() or _is_placeholder(value) or _looks_like_code(value):
                continue
            findings.append(
                Finding(ERROR, rel_path, number, "secret:assigned-value",
                        "`%s` is assigned a literal value: %s" % (name, _redact(value)))
            )

        for match in _HEX_BLOB_RE.finditer(line):
            findings.append(
                Finding(ERROR, rel_path, number, "secret:hex-blob",
                        "%d-character hex string: %s"
                        % (len(match.group(0)), _redact(match.group(0))))
            )

        for match in _TOKEN_CANDIDATE_RE.finditer(line):
            token = match.group(0)
            if _HEX_BLOB_RE.fullmatch(token):
                continue
            reason = _high_entropy_reason(token)
            if reason:
                findings.append(
                    Finding(ERROR, rel_path, number, "secret:high-entropy",
                            "high-entropy string (%s): %s" % (reason, _redact(token)))
                )

    return _dedupe(findings)


def _redact(value: str) -> str:
    if len(value) <= 8:
        return value[:2] + "*" * (len(value) - 2)
    return "%s...%s (%d chars)" % (value[:4], value[-2:], len(value))


def _dedupe(findings: List[Finding]) -> List[Finding]:
    seen = set()
    unique = []
    for finding in findings:
        marker = (finding.path, finding.line, finding.rule, finding.message)
        if marker not in seen:
            seen.add(marker)
            unique.append(finding)
    return unique


def scannable_files(repo_root: Path) -> List[Path]:
    """Text files git would consider part of the working tree."""
    paths = _git_listed_files(repo_root)
    if paths is None:
        paths = [
            p
            for p in repo_root.rglob("*")
            if p.is_file() and not (SKIP_DIRS & set(p.relative_to(repo_root).parts))
        ]
    return sorted(
        (p for p in paths if p.is_file() and p.suffix.lower() not in SKIP_SUFFIXES),
        key=lambda p: p.as_posix(),
    )


def _git_listed_files(repo_root: Path) -> Optional[List[Path]]:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    names = [n for n in completed.stdout.decode("utf-8", "replace").split("\0") if n]
    return [repo_root / name for name in names]


def scan_repository(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for path in scannable_files(repo_root):
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        findings.extend(scan_text_for_secrets(text, rel_path))
    return findings


# --- reporting --------------------------------------------------------------


def render(findings: List[Finding], documents: List[Document], scanned: int) -> str:
    lines: List[str] = []
    errors = [f for f in findings if f.level == ERROR]
    warnings = [f for f in findings if f.level == WARNING]
    secrets = [f for f in errors if f.rule.startswith("secret:")]

    by_path: Dict[str, List[Finding]] = {}
    for finding in findings:
        by_path.setdefault(finding.path, []).append(finding)

    for path in sorted(by_path):
        lines.append(path)
        for finding in sorted(by_path[path], key=lambda f: (f.line or 0, f.rule)):
            location = str(finding.line) if finding.line else "-"
            lines.append(
                "  %-7s %s:%s  %s  %s"
                % (finding.level, path, location, finding.rule, finding.message)
            )
        lines.append("")

    if secrets:
        lines.append("!" * 68)
        lines.append("CREDENTIAL SCAN FAILED: %d suspected secret(s)." % len(secrets))
        lines.append("Nothing here should hold a live credential. Remove the value,")
        lines.append("rotate it, and reference the secret by name instead.")
        lines.append("If a match is a false positive, append `%s` to the line." % ALLOW_PRAGMA)
        lines.append("!" * 68)
        lines.append("")

    lines.append(
        "%d document(s) checked, %d file(s) scanned: %d error(s), %d warning(s)."
        % (len(documents), scanned, len(errors), len(warnings))
    )
    if not doclib.HAVE_PYYAML:
        lines.append(
            "note: PyYAML is not installed; frontmatter was parsed with the "
            "built-in subset parser."
        )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path,
                        help="specific documents to check (default: all)")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit findings as JSON")
    parser.add_argument("--max-age-days", type=int, default=0, metavar="N",
                        help="warn when a piloted/proven document is older than N days")
    parser.add_argument("--no-secret-scan", action="store_true",
                        help="skip the credential scan")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()

    if args.paths:
        doc_paths = [p.resolve() for p in args.paths]
    else:
        doc_paths = doclib.iter_doc_paths(repo_root)

    documents = [doclib.read_document(p, repo_root) for p in doc_paths]

    findings: List[Finding] = []
    for document in documents:
        findings.extend(check_document(document, max_age_days=args.max_age_days))

    scanned = 0
    if not args.no_secret_scan:
        files = scannable_files(repo_root)
        scanned = len(files)
        findings.extend(scan_repository(repo_root))

    errors = [f for f in findings if f.level == ERROR]
    warnings = [f for f in findings if f.level == WARNING]

    if args.as_json:
        print(json.dumps(
            {
                "documents_checked": len(documents),
                "files_scanned": scanned,
                "errors": len(errors),
                "warnings": len(warnings),
                "findings": [asdict(f) for f in findings],
            },
            indent=2,
            sort_keys=True,
        ))
    else:
        print(render(findings, documents, scanned))

    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
