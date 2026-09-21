"""Content-addressed outputs and bounded atomic JSON journals."""

import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(6):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                # Windows readers/antivirus may briefly hold a non-delete-sharing
                # handle. Keep the old complete journal intact and retry replace.
                if attempt == 5:
                    raise
                time.sleep(0.01 * (2**attempt))
    finally:
        temporary.unlink(missing_ok=True)


def file_evidence(path, *, root=None):
    path = Path(path).resolve()
    if root is not None and Path(root).resolve() not in path.parents:
        raise ValueError("Artifact is outside the workflow output directory")
    if not path.is_file() or not 0 < path.stat().st_size <= 2_000_000_000:
        raise ValueError("Artifact is missing, empty or exceeds 2 GB")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def verify_evidence(record, *, root=None):
    if not isinstance(record, dict) or not record.get("sha256"):
        raise ValueError("Artifact has no integrity evidence; revalidate before recovery")
    actual = file_evidence(record["path"], root=root)
    if any(actual[key] != record.get(key) for key in ("bytes", "sha256")):
        raise ValueError("Artifact content changed since validation; recovery is blocked")
    return actual
