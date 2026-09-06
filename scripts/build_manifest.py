#!/usr/bin/env python3
"""Build manifest.json, the index an agent reads to decide what to load.

Walks context/ and skills/ and writes one entry per document: its name,
description, validation status and path. Templates (files whose name starts
with an underscore) are skipped.

    python3 scripts/build_manifest.py            # write manifest.json
    python3 scripts/build_manifest.py --check    # fail if it is out of date
    python3 scripts/build_manifest.py --stdout   # print without writing

Output is sorted and carries no timestamp, so rebuilding an unchanged tree
produces a byte-identical file and --check works as a CI gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import doclib
from doclib import REPO_ROOT, VALIDATION_STATUSES, Document

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"


def document_entry(document: Document) -> Dict[str, Any]:
    meta = document.meta
    sources = meta.get("sources") or []
    if not isinstance(sources, list):
        sources = [sources]

    return {
        "name": meta.get("name") or document.stem,
        "path": document.rel_path,
        "collection": document.collection,
        "type": meta.get("type"),
        "description": meta.get("description"),
        "validation_status": meta.get("validation_status"),
        "last_validated": meta.get("last_validated"),
        "sources": [str(s) for s in sources],
        "sections": [text for level, _, text in document.headings if level == 2],
    }


def build_manifest(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    documents = [
        document
        for document in doclib.load_documents(repo_root)
        if not document.is_template
    ]

    entries: List[Dict[str, Any]] = []
    unreadable: List[Dict[str, str]] = []
    for document in documents:
        if document.parse_error:
            unreadable.append({"path": document.rel_path, "error": document.parse_error})
            continue
        entries.append(document_entry(document))

    entries.sort(key=lambda e: (e["collection"], e["path"]))

    by_status = {status: 0 for status in VALIDATION_STATUSES}
    by_collection: Dict[str, int] = {}
    for entry in entries:
        status = entry.get("validation_status")
        if isinstance(status, str):
            by_status[status] = by_status.get(status, 0) + 1
        collection = entry.get("collection") or ""
        by_collection[collection] = by_collection.get(collection, 0) + 1

    manifest: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "validation_statuses": list(VALIDATION_STATUSES),
        "counts": {
            "documents": len(entries),
            "by_status": by_status,
            "by_collection": dict(sorted(by_collection.items())),
        },
        "documents": entries,
    }
    if unreadable:
        manifest["unreadable"] = sorted(unreadable, key=lambda u: u["path"])
    return manifest


def serialize(manifest: Dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=None,
                        help="where to write (default: <repo-root>/manifest.json)")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the file on disk differs from a fresh build")
    parser.add_argument("--stdout", action="store_true",
                        help="print the manifest instead of writing it")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    output = (args.output or repo_root / MANIFEST_NAME).resolve()

    manifest = build_manifest(repo_root)
    rendered = serialize(manifest)

    if manifest.get("unreadable"):
        for item in manifest["unreadable"]:
            print("warning: %s could not be parsed: %s" % (item["path"], item["error"]),
                  file=sys.stderr)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    if args.check:
        if not output.exists():
            print("%s is missing; run scripts/build_manifest.py" % output.name, file=sys.stderr)
            return 1
        if output.read_text(encoding="utf-8") != rendered:
            print("%s is out of date; run scripts/build_manifest.py" % output.name,
                  file=sys.stderr)
            return 1
        print("%s is up to date (%d document(s))." % (output.name, len(manifest["documents"])))
        return 0

    output.write_text(rendered, encoding="utf-8")
    print("Wrote %s: %d document(s) %s."
          % (output.name, len(manifest["documents"]),
             ", ".join("%d %s" % (count, status)
                       for status, count in manifest["counts"]["by_status"].items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
