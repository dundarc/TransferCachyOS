import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

RESTIC = "/usr/bin/restic"


def backup_plan(sources, destination):
    try:
        paths = tuple(dict.fromkeys(Path(source).resolve(strict=True) for source in sources))
        target = Path(destination).resolve(strict=True)
        if not paths or not target.is_dir() or not all(path.is_dir() for path in paths):
            raise ValueError("invalid")
        if any(target.is_relative_to(path) or path.is_relative_to(target) for path in paths):
            raise ValueError("invalid")
        if (target / "config").is_file():
            return paths, target, False
        if not any(target.iterdir()):
            return paths, target, True
    except (OSError, RuntimeError) as error:
        raise ValueError("invalid") from error
    raise ValueError("target_error")


def backup_identity(paths, target):
    return tuple((stat.st_dev, stat.st_ino) for stat in (path.stat() for path in (*paths, target)))


def repository_fingerprint(target):
    config = target / "config"
    if not config.is_file():
        return None
    with config.open("rb") as handle:
        data = handle.read(65537)
    if not data or len(data) > 65536:
        return None
    return hashlib.sha256(data).hexdigest()


def restore_destination(path, repository):
    try:
        destination = Path(path).resolve(strict=True)
        if (
            destination.is_dir()
            and not destination.is_relative_to(repository)
            and not repository.is_relative_to(destination)
            and not any(destination.iterdir())
        ):
            return destination
    except (OSError, RuntimeError):
        pass
    raise ValueError("restore_invalid")


def snapshot_rows(payload):
    snapshots = json.loads(payload)
    if not isinstance(snapshots, list):
        raise ValueError("Invalid snapshot list")
    rows = []
    for snapshot in snapshots:
        ref = snapshot["id"]
        if not re.fullmatch(r"[0-9a-f]{64}", ref):
            raise ValueError("Invalid snapshot ID")
        timestamp = datetime.fromisoformat(snapshot["time"]).astimezone()
        paths = ", ".join(snapshot["paths"])
        rows.append((timestamp, ref, paths))
    return sorted(rows, reverse=True)
