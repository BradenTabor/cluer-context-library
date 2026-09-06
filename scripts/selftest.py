#!/usr/bin/env python3
"""Self-test for validate.py.

A credential scanner that has never been shown a credential is indistinguishable
from one that does nothing, and a scanner tuned only against real secrets buries
you in false positives. So this checks both directions: strings that must be
caught, and strings taken verbatim from this repo's documents that must not be.

    python3 scripts/selftest.py

Exit status is 0 when every case behaves as expected.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

import doclib
import validate

# Fabricated, structurally valid, never live. Each source line carries the
# allow pragma so the repo-wide scan does not flag this file.
MUST_DETECT: Tuple[Tuple[str, str], ...] = (
    ("openai key", "OPENAI_API_KEY=sk-proj-T3xQv7Rm2NpLb9Wd4Kf6Hs1Zc8Yj5Gt0Aq"),  # pragma: allow-secret
    ("github token", "token: ghp_9QwErTyUiOpAsDfGhJkLzXcVbNm1234567890"),  # pragma: allow-secret
    ("aws access id", "aws_access_key_id = AKIAIOSFODNN7EXAMPLE"),  # pragma: allow-secret
    ("aws secret", "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYzKm4Qd7Vn"),  # pragma: allow-secret
    ("stripe key", "STRIPE=sk_live_4eC39HqLyjWDarjtT1zdp7dc"),  # pragma: allow-secret
    ("slack token", "xoxb-2401-5837-QpZm7Wv3Rk9Tn2Bx6Ld4Hs8Y"),  # pragma: allow-secret
    ("private key block", "-----BEGIN RSA PRIVATE KEY-----"),  # pragma: allow-secret
    ("json web token", "auth: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NX0.dBjftJeZ4CVPmB92K27u"),  # pragma: allow-secret
    ("hex blob", "digest = 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"),  # pragma: allow-secret
    ("plain password", "password: Zk7#mQ2vRt9Xw"),  # pragma: allow-secret
    ("api key literal", "api_key: 7fQ2mVx9Lp4Rt6Bn3Ws8Kd5Hy1Zc"),  # pragma: allow-secret
)

# Every one of these is real text from context/helm-config-architecture.md or a
# shape it uses. A hit here is a false positive that would train people to
# ignore the scanner.
MUST_IGNORE: Tuple[Tuple[str, str], ...] = (
    ("systemd env line", "OLLAMA_CONTEXT_LENGTH=65536"),
    ("sandbox config path", "infra/openshell/hermes-sandbox/config.yaml"),
    ("systemd unit path", "infra/systemd/ollama-code-lane.override.conf"),
    ("test path", "packages/contracts/__tests__/sandbox-model-routes.test.ts"),
    ("commission script", "scripts/commission-hermes-sandbox-appdev1.sh"),
    ("configure script", "scripts/configure-dual-ollama-appdev1.sh"),
    ("handoff doc", "docs/HERMES_HELM_HANDOFF.md"),
    ("home path", "$HOME/Projects/Hermes/hermes-worker/deploy/"),
    ("contracts marker", 'contracts: ["quality-evidence-v1"]'),
    ("json config key", "maximumContextTokens: 8192"),
    ("nvidia command", "nvidia-smi --query-gpu=memory.used --format=csv"),
    ("docker command", "docker exec cluer-ollama-code ollama ps"),
    ("commit reference", 'commit b06f1d6 ("Reserve output room in Hermes\' context budget")'),
    ("key_env mention", "Any check that needs to resolve `key_env` values"),
    ("budget arithmetic", "context_length + max_output_tokens  <=  laneWindow"),
    ("env indirection", "API_KEY=${VAULT_TOKEN}"),
    ("placeholder token", "token: <your-token-here>"),
    ("redacted secret", "CLIENT_SECRET=redacted"),
    ("numeric token limit", "MAX_TOKENS=131072"),
    ("uuid", "run-id: 550e8400-e29b-41d4-a716-446655440000"),
)

VALID_DOC = """---
name: sample-doc
type: project
description: A syntactically complete document used to exercise the validator.
validation_status: proven
last_validated: 2026-01-15
sources:
  - some/file.ts
---

# Sample doc

## Why this document exists

Because the validator needs something that passes.

## Gotchas

One that actually happened.

## Conventions

A standing rule.

## Off-limits

Something not to touch.

## Definition of done

1. It validates.
"""


def _rules(text: str) -> List[str]:
    return [f.rule for f in validate.scan_text_for_secrets(text, "sample")]


def _doc_rules(body: str, filename: str = "sample-doc.md") -> List[str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "context").mkdir()
        path = root / "context" / filename
        path.write_text(body, encoding="utf-8")
        document = doclib.read_document(path, root)
        return [f.rule for f in validate.check_document(document)]


def run() -> int:
    failures: List[str] = []

    for label, sample in MUST_DETECT:
        if not _rules(sample):
            failures.append("missed a credential: %s" % label)

    for label, sample in MUST_IGNORE:
        hits = _rules(sample)
        if hits:
            failures.append("false positive on %s: %s" % (label, ", ".join(sorted(set(hits)))))

    # The reference document and the template both have to stay clean.
    for relative in ("context/helm-config-architecture.md", "context/_TEMPLATE.md"):
        path = doclib.REPO_ROOT / relative
        if path.exists():
            document = doclib.read_document(path)
            errors = [f for f in validate.check_document(document) if f.level == validate.ERROR]
            if errors:
                failures.append(
                    "%s should validate cleanly, got: %s"
                    % (relative, "; ".join(f.message for f in errors))
                )

    if _doc_rules(VALID_DOC):
        failures.append("a well-formed document was rejected")

    structural: Tuple[Tuple[str, str, str, str], ...] = (
        ("missing field", VALID_DOC.replace("type: project\n", ""), "missing-field", "sample-doc.md"),
        ("bad status", VALID_DOC.replace("proven", "verified"), "validation-status", "sample-doc.md"),
        ("name mismatch", VALID_DOC, "name-filename-mismatch", "other-name.md"),
        ("missing section", VALID_DOC.replace("## Conventions", "## Notes"), "missing-section", "sample-doc.md"),
        ("no frontmatter", VALID_DOC.split("---\n", 2)[2], "frontmatter", "sample-doc.md"),
        ("date required when piloted",
         VALID_DOC.replace("last_validated: 2026-01-15", "last_validated:"),
         "last-validated", "sample-doc.md"),
        ("bad date", VALID_DOC.replace("2026-01-15", "15/01/2026"), "last-validated", "sample-doc.md"),
    )
    for label, body, expected, filename in structural:
        if expected not in _doc_rules(body, filename):
            failures.append("expected %s for %r, got %s" % (expected, label, _doc_rules(body, filename)))

    # A blank last_validated is allowed only while unvalidated.
    unvalidated = VALID_DOC.replace("proven", "unvalidated").replace(
        "last_validated: 2026-01-15", "last_validated:"
    )
    if "last-validated" in _doc_rules(unvalidated):
        failures.append("blank last_validated should be allowed when unvalidated")

    # The pragma has to actually suppress a hit.
    suppressed = "password: Zk7#mQ2vRt9Xw  # pragma: allow-secret"
    if validate.ALLOW_PRAGMA not in suppressed or _rules(suppressed):
        failures.append("allow pragma did not suppress a finding")

    total = len(MUST_DETECT) + len(MUST_IGNORE) + len(structural) + 4
    if failures:
        print("FAILED (%d of %d checks)" % (len(failures), total))
        for failure in failures:
            print("  - %s" % failure)
        return 1

    print("ok: %d checks passed (%d detections, %d non-detections, %d structural)"
          % (total, len(MUST_DETECT), len(MUST_IGNORE), len(structural)))
    return 0


if __name__ == "__main__":
    sys.exit(run())
