"""Create or verify the integrity manifest for a local backup bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ARTIFACTS = ("database.dump", "database-counts.json", "documents.tar.gz", "documents.json")


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def create(args: argparse.Namespace) -> None:
    root = args.directory.resolve()
    artifacts = {
        name: {"bytes": (root / name).stat().st_size, "sha256": digest(root / name)}
        for name in ARTIFACTS
    }
    counts = load_json(root / "database-counts.json")
    documents = load_json(root / "documents.json")
    manifest = {
        "schema_version": 1,
        "created_at": args.created_at,
        "git_revision": args.git_revision,
        "source_database": args.source_database,
        "database_counts": counts,
        "document_file_count": len(documents["files"]),
        "artifacts": artifacts,
        "restore_policy": "isolated-target-only",
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify(args: argparse.Namespace) -> None:
    root = args.directory.resolve()
    manifest = load_json(root / "manifest.json")
    if manifest.get("schema_version") != 1:
        raise SystemExit("Unsupported backup manifest schema")
    if manifest.get("restore_policy") != "isolated-target-only":
        raise SystemExit("Backup is missing the isolated restore policy")
    expected = set(ARTIFACTS)
    if set(manifest.get("artifacts", {})) != expected:
        raise SystemExit("Backup artifact set does not match the supported bundle")
    for name in ARTIFACTS:
        path = root / name
        record = manifest["artifacts"][name]
        if not path.is_file():
            raise SystemExit(f"Missing backup artifact: {name}")
        if path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
            raise SystemExit(f"Backup artifact failed integrity check: {name}")
    print("Backup manifest integrity verified.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--directory", type=Path, required=True)
    create_parser.add_argument("--output", type=Path, required=True)
    create_parser.add_argument("--created-at", required=True)
    create_parser.add_argument("--git-revision", required=True)
    create_parser.add_argument("--source-database", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--directory", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "create":
        create(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
