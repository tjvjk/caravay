"""Inspect, acquire, and publish Caravay's managed model snapshot."""

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal, TextIO

from filelock import FileLock, Timeout
from huggingface_hub import HfApi, RepoFile, snapshot_download
from huggingface_hub.utils.tqdm import disable_progress_bars

from caravay.settings import Settings

State = Literal["ready", "missing", "invalid"]
SPACE: Final = 20 * 1024**3


@dataclass(frozen=True)
class Expected:
    """Describe trusted metadata for one pinned repository file."""

    path: str
    size: int
    checksum: str
    algorithm: Literal["sha1", "sha256"]


FILES: Final = (
    "added_tokens.json",
    "config.json",
    "generation_config.json",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
    "model.safetensors.index.json",
    "preprocessor_config.json",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.model",
    "tokenizer_config.json",
)


class DownloadError(RuntimeError):
    """Signal that a model snapshot could not be downloaded safely."""


class DownloadLockError(RuntimeError):
    """Signal that another process is downloading the model snapshot."""


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
                and all(paths)
                and len(set(paths)) == len(paths)
                and set(paths) == set(FILES)
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


def hashes(path: Path, size: int) -> tuple[str, str]:
    """Return SHA-256 and Git-blob SHA-1 in one pass over a repository file."""
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1(usedforsecurity=False)
    sha1.update(f"blob {size}\0".encode())
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            sha256.update(block)
            sha1.update(block)
    return sha256.hexdigest(), sha1.hexdigest()


def recover(root: Path, snapshot: Path, quarantine: Path) -> bool:
    """Recover quarantine left by an interrupted publication."""
    if not quarantine.exists():
        return False
    if not snapshot.exists():
        quarantine.replace(snapshot)
        return True
    if inspect(root) == "ready":
        shutil.rmtree(quarantine)
        return True
    shutil.rmtree(snapshot)
    quarantine.replace(snapshot)
    return True


def require(root: Path) -> bool:
    """Require the download safety margin on the destination filesystem."""
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < SPACE:
        raise DownloadError("destination filesystem has less than 20 GiB free")
    return True


def expected() -> tuple[Expected, ...]:
    """Fetch trusted checksums for every file at the pinned revision."""
    values = HfApi().get_paths_info(
        Settings.repository_name,
        list(FILES),
        revision=Settings.revision,
    )
    result: list[Expected] = []
    for value in values:
        match value:
            case RepoFile() as item if item.path in FILES and item.lfs is not None:
                result.append(Expected(item.path, item.size, item.lfs.sha256, "sha256"))
            case RepoFile() as item if item.path in FILES:
                result.append(Expected(item.path, item.size, item.blob_id, "sha1"))
            case _:
                raise DownloadError("pinned repository returned invalid file metadata")
    if {item.path for item in result} != set(FILES):
        raise DownloadError("pinned repository does not contain every required file")
    return tuple(result)


def prepare(staging: Path) -> Path:
    """Download the exact pinned runtime files with the standard Hub client."""
    return Path(
        snapshot_download(
            repo_id=Settings.repository_name,
            revision=Settings.revision,
            local_dir=staging,
            allow_patterns=list(FILES),
        )
    )


def record(staging: Path, expected: tuple[Expected, ...]) -> bool:
    """Create and fully verify the manifest for staged runtime files."""
    entries: list[dict[str, object]] = []
    for item in expected:
        target = staging / item.path
        sha256, sha1 = hashes(target, item.size)
        actual = sha1 if item.algorithm == "sha1" else sha256
        if target.stat().st_size != item.size or actual != item.checksum:
            raise DownloadError(f"staged file failed verification: {item.path}")
        entries.append({"path": item.path, "size": item.size, "sha256": sha256})
    document = {
        "manifest_version": Settings.manifest_version,
        "backend": Settings.backend_name,
        "repository": Settings.repository_name,
        "revision": Settings.revision,
        "files": entries,
    }
    temporary = staging / f"{Settings.manifest_name}.tmp"
    temporary.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
    temporary.replace(staging / Settings.manifest_name)
    cache = staging / ".cache"
    if cache.exists():
        shutil.rmtree(cache)
    return True


def publish(staging: Path, snapshot: Path, quarantine: Path) -> bool:
    """Atomically publish staging while preserving an invalid prior snapshot."""
    replaced = snapshot.exists()
    if replaced:
        snapshot.replace(quarantine)
    try:
        staging.replace(snapshot)
    except OSError:
        if replaced and quarantine.exists() and not snapshot.exists():
            quarantine.replace(snapshot)
        raise
    if quarantine.exists():
        shutil.rmtree(quarantine)
    return True


def download(root: Path, progress: TextIO = sys.stderr) -> bool:
    """Acquire and atomically publish the one pinned model snapshot."""
    base = root / Settings.backend_name
    snapshot = base / Settings.revision
    staging = base / f"{Settings.revision}.partial"
    quarantine = base / f"{Settings.revision}.quarantine"
    base.mkdir(parents=True, exist_ok=True)
    lock = FileLock(base / f"{Settings.revision}.lock")
    try:
        with lock.acquire(timeout=0):
            recover(root, snapshot, quarantine)
            if inspect(root) == "ready":
                return False
            require(root)
            if not progress.isatty():
                disable_progress_bars()
            inventory = expected()
            prepare(staging)
            record(staging, inventory)
            publish(staging, snapshot, quarantine)
            return True
    except Timeout as error:
        raise DownloadLockError("another model download is in progress") from error
    except DownloadError:
        raise
    except Exception as error:
        raise DownloadError(f"model download failed: {error}") from error
