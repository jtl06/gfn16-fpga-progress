"""Verify checked-out upstream revisions and locked source-file hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def verify_repository(spec: dict[str, object], root: Path) -> None:
    expected_commit = str(spec["commit"])
    actual_commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_commit != expected_commit:
        raise SystemExit(f"{spec['name']}: commit {actual_commit} != {expected_commit}")
    files = spec["files"]
    if not isinstance(files, dict):
        raise SystemExit(f"{spec['name']}: malformed file lock")
    for relative, expected_hash in files.items():
        payload = (root / relative).read_bytes()
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != expected_hash:
            raise SystemExit(f"{spec['name']}:{relative}: SHA-256 mismatch")
    print(f"{spec['name']}: PASS {expected_commit} ({len(files)} files)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genefer-root", type=Path, required=True)
    parser.add_argument("--catapult-root", type=Path, required=True)
    args = parser.parse_args()
    lock_path = Path(__file__).resolve().parents[1] / "config" / "upstreams.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    roots = {"genefer22": args.genefer_root, "catapult-microsoft-pcie": args.catapult_root}
    for repository in lock["repositories"]:
        verify_repository(repository, roots[repository["name"]])


if __name__ == "__main__":
    main()

