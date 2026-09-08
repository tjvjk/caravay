"""Translate supported text with the pinned managed backend."""

import importlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, NotRequired, Protocol, TextIO, TypedDict, cast

from caravay.models import inspect
from caravay.settings import LANGUAGES, Backend, Settings

Outcome = Literal["completed", "degraded", "skipped", "failed"]
Format = Literal["text", "jsonl"]
Stage = Literal["text_to_text"]
FORMAT: Final[tuple[Format, ...]] = ("text", "jsonl")
LANGUAGE: Final = re.compile(r"[a-z]{3}\Z")


class IssueDocument(TypedDict):
    """Define one schema-version-one issue object."""

    stage: Stage
    code: str
    message: str


class CountsDocument(TypedDict):
    """Define schema-version-one segment counts."""

    total: int
    completed: int
    degraded: int
    skipped: int
    failed: int


class BackendsDocument(TypedDict):
    """Define the resolved translation backend bindings."""

    text_to_text: Backend


class SegmentDocument(TypedDict):
    """Define one schema-version-one segment record."""

    schema_version: Literal[1]
    type: Literal["segment"]
    index: int
    outcome: Outcome
    text: str | None
    issues: list[IssueDocument]


class SummaryDocument(TypedDict):
    """Define one schema-version-one translation summary."""

    schema_version: Literal[1]
    type: Literal["summary"]
    command: Literal["translate"]
    outcome: Outcome
    source_language: str
    target_language: str
    backends: BackendsDocument
    segments: CountsDocument
    error: NotRequired[IssueDocument]


Document = SegmentDocument | SummaryDocument


@dataclass(frozen=True)
class Issue:
    """Describe one machine-readable text translation issue."""

    stage: Stage
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
    return cast(Runtime, importlib.import_module("caravay.runtime"))


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


def capability(backend: str, source: str, target: str) -> Backend:
    """Validate the named backend's language-qualified text capability."""
    if (
        backend != Settings.backend_name
        or source not in LANGUAGES
        or target not in LANGUAGES
    ):
        raise ValidationError(
            f"unsupported_capability: {backend} cannot translate {source} to {target}"
        )
    return cast(Backend, backend)


def validate(root: Path, verbose: bool) -> Path:
    """Require a ready snapshot and an available MPS runtime in order."""
    state = inspect(root)
    if state == "missing":
        raise ValidationError(
            "model_not_installed: run caravay models download before translation"
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


def issue(value: Issue) -> IssueDocument:
    """Serialize one issue for schema version one."""
    return {"stage": value.stage, "code": value.code, "message": value.message}


def summary(
    outcome: Outcome, source: str, target: str, backend: Backend, total: int
) -> SummaryDocument:
    """Build a schema-version-one translation summary."""
    counts: CountsDocument = {
        "total": total,
        "completed": int(total > 0 and outcome == "completed"),
        "degraded": int(total > 0 and outcome == "degraded"),
        "skipped": int(total > 0 and outcome == "skipped"),
        "failed": int(total > 0 and outcome == "failed"),
    }
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


def segment(result: Result) -> SegmentDocument:
    """Build one schema-version-one translation segment."""
    return {
        "schema_version": 1,
        "type": "segment",
        "index": 0,
        "outcome": result.outcome,
        "text": result.text or None,
        "issues": [issue(value) for value in result.issues],
    }


def dump(document: Document) -> str:
    """Serialize one typed schema-version-one document as compact JSONL."""
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"


def write(stream: TextIO, result: Result, representation: Format) -> bool:
    """Write one translation result in the selected representation."""
    if representation == "text":
        if result.text:
            stream.write(f"{result.text.strip()}\n")
        return True
    stream.write(dump(segment(result)))
    return True


def finish(
    stream: TextIO,
    result: Result,
    representation: Format,
    source: str,
    target: str,
    backend: Backend,
) -> bool:
    """Write the terminal translation summary when selected."""
    if representation == "text":
        return True
    terminal = summary(result.outcome, source, target, backend, 1)
    if result.outcome == "failed":
        terminal["error"] = issue(result.issues[-1])
    stream.write(dump(terminal))
    return True


def emit(
    stream: TextIO,
    result: Result,
    representation: Format,
    source: str,
    target: str,
    backend: Backend,
) -> bool:
    """Write one translation result and its terminal summary."""
    write(stream, result, representation)
    finish(stream, result, representation, source, target, backend)
    return True


def empty(
    stream: TextIO,
    representation: Format,
    source: str,
    target: str,
    backend: Backend,
) -> bool:
    """Write the skipped representation for empty valid input."""
    if representation == "jsonl":
        stream.write(dump(summary("skipped", source, target, backend, 0)))
    return True
