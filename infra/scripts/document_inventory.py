"""Print a deterministic JSON inventory for a document storage directory."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: document_inventory.py STORAGE_ROOT")
    root = Path(sys.argv[1])
    files = []
    if root.exists():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
    print(json.dumps({"schema_version": 1, "files": files}, sort_keys=True))


if __name__ == "__main__":
    main()
