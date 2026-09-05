"""Inspect Caraway's managed model snapshot."""

import json
from pathlib import Path, PurePosixPath
from typing import Literal

from caraway.settings import Settings

State = Literal["ready", "missing", "invalid"]


def exact(value: object, keys: frozenset[str]) -> bool:
    """Return whether a value is a mapping with exactly the expected keys."""
    match value:
        case dict() as mapping:
            return set(mapping) == keys
        case _:
            return False


def safe(value: str) -> bool:
    """Return whether a manifest path stays within its snapshot."""
    path = PurePosixPath(value)
    return (
        bool(value)
        and not path.is_absolute()
        and ".." not in path.parts
        and str(path) == value
    )


def digest(value: str) -> bool:
    """Return whether a value is a lowercase SHA-256 digest."""
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def entry(value: object, snapshot: Path) -> bool:
    """Verify one expected-file manifest entry without hashing its contents."""
    match value:
        case {"path": str() as path, "size": bool(), "sha256": str()}:
            return False
        case {
            "path": str() as path,
            "size": int() as size,
            "sha256": str() as checksum,
        } if exact(value, frozenset(("path", "size", "sha256"))):
            target = snapshot.joinpath(*PurePosixPath(path).parts)
            try:
                return (
                    safe(path)
                    and size >= 0
                    and digest(checksum)
                    and target.is_file()
                    and target.stat().st_size == size
                )
            except OSError:
                return False
        case _:
            return False


def name(value: object) -> str:
    """Return an expected-file path or an invalid empty sentinel."""
    match value:
        case {"path": str() as path}:
            return path
        case _:
            return ""


def valid(value: object, snapshot: Path) -> bool:
    """Verify the pinned identity, manifest shape, and every expected file."""
    match value:
        case {"manifest_version": bool()}:
            return False
        case {
            "manifest_version": int() as version,
            "backend": str() as backend,
            "repository": str() as repository,
            "revision": str() as revision,
            "files": list() as files,
        } if exact(
            value,
            frozenset(
                ("manifest_version", "backend", "repository", "revision", "files")
            ),
        ):
            paths = tuple(name(item) for item in files)
            return (
                version == Settings.manifest_version
                and backend == Settings.backend_name
                and repository == Settings.repository_name
                and revision == Settings.revision
                and bool(files)
                and all(paths)
                and len(set(paths)) == len(paths)
                and all(entry(item, snapshot) for item in files)
            )
        case _:
            return False


def inspect(root: Path) -> State:
    """Report the state of the pinned snapshot below a managed cache root."""
    snapshot = root / Settings.backend_name / Settings.revision
    if not snapshot.exists():
        return "missing"
    try:
        document: object = json.loads(
            (snapshot / Settings.manifest_name).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "invalid"
    return "ready" if valid(document, snapshot) else "invalid"
