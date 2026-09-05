"""Translate Source Armenian text with the pinned managed backend."""

import importlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol, TextIO, cast

from caraway.models import inspect
from caraway.settings import Settings

Outcome = Literal["completed", "degraded", "skipped", "failed"]
FORMAT: Final = ("text", "jsonl")
LANGUAGE: Final = re.compile(r"[a-z]{3}\Z")


@dataclass(frozen=True)
class Issue:
    """Describe one machine-readable text translation issue."""

    stage: Literal["text_to_text"]
    code: str
    message: str


@dataclass(frozen=True)
class Result:
    """Hold one translated segment and its observable outcome."""

    outcome: Outcome
    text: str
    issues: tuple[Issue, ...]


class ValidationError(ValueError):
    """Signal that translation cannot safely start."""


class Runtime(Protocol):
    """Describe the lazily imported heavyweight backend module."""

    def validate(self, verbose: bool) -> bool:
        """Require the configured runtime device."""
        ...

    def translate(self, path: Path, source: str, target: str, text: str) -> Result:
        """Translate one text segment."""
        ...


def runtime() -> Runtime:
    """Load the heavyweight backend module only after local validation."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return cast(Runtime, importlib.import_module("caraway.runtime"))


def snapshot(root: Path) -> Path:
    """Resolve the explicit installed snapshot path."""
    return root / Settings.backend_name / Settings.revision


def language(value: str) -> str:
    """Accept one canonical lowercase ISO 639-3 language code."""
    if LANGUAGE.fullmatch(value) is None:
        raise ValidationError(
            f"invalid_language: {value} is not a lowercase ISO 639-3 code"
        )
    return value


def capability(backend: str, source: str, target: str) -> bool:
    """Validate the named backend's language-qualified text capability."""
    if backend != Settings.backend_name or source != "hye" or target != "eng":
        raise ValidationError(
            f"unsupported_capability: {backend} cannot translate {source} to {target}"
        )
    return True


def validate(root: Path, verbose: bool) -> Path:
    """Require a ready snapshot and an available MPS runtime in order."""
    state = inspect(root)
    if state == "missing":
        raise ValidationError(
            "model_not_installed: run caraway models download before translation"
        )
    if state == "invalid":
        raise ValidationError(
            "model_cache_invalid: installed model snapshot is invalid"
        )
    runtime().validate(verbose)
    return snapshot(root)


def translate(path: Path, source: str, target: str, text: str) -> Result:
    """Translate one text segment offline on MPS with FP16."""
    return runtime().translate(path, source, target, text)


def trim(text: str) -> str:
    """Remove a suffix made from three or more identical generated phrases."""
    matches = tuple(re.finditer(r"\S+", text))
    words = tuple(value.group() for value in matches)
    for size in range(1, len(words) // 3 + 1):
        suffix = words[-size:]
        repeats = 1
        while (
            size * (repeats + 1) <= len(words)
            and words[-size * (repeats + 1) : -size * repeats] == suffix
        ):
            repeats += 1
        if repeats >= 3:
            start = matches[len(words) - size * repeats].start()
            return text[:start].rstrip()
    return text


def issue(value: Issue) -> dict[str, str]:
    """Serialize one issue for schema version one."""
    return {"stage": value.stage, "code": value.code, "message": value.message}


def summary(
    outcome: Outcome, source: str, target: str, backend: str, total: int
) -> dict[str, object]:
    """Build a schema-version-one translation summary."""
    counts = {"total": total, "completed": 0, "degraded": 0, "skipped": 0, "failed": 0}
    if total:
        counts[outcome] = 1
    return {
        "schema_version": 1,
        "type": "summary",
        "command": "translate",
        "outcome": outcome,
        "source_language": source,
        "target_language": target,
        "backends": {"text_to_text": backend},
        "segments": counts,
    }


def emit(
    stream: TextIO,
    result: Result,
    representation: str,
    source: str,
    target: str,
    backend: str,
) -> bool:
    """Write one translation result in the selected stdout format."""
    if representation == "text":
        if result.text:
            stream.write(f"{result.text.strip()}\n")
        return True
    segment = {
        "schema_version": 1,
        "type": "segment",
        "index": 0,
        "outcome": result.outcome,
        "text": result.text or None,
        "issues": [issue(value) for value in result.issues],
    }
    stream.write(json.dumps(segment, ensure_ascii=False, separators=(",", ":")) + "\n")
    terminal = summary(result.outcome, source, target, backend, 1)
    if result.outcome == "failed":
        terminal["error"] = issue(result.issues[-1])
    stream.write(
        json.dumps(
            terminal,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    return True


def empty(
    stream: TextIO,
    representation: str,
    source: str,
    target: str,
    backend: str,
) -> bool:
    """Write the skipped representation for empty valid input."""
    if representation == "jsonl":
        stream.write(
            json.dumps(
                summary("skipped", source, target, backend, 0),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
    return True
