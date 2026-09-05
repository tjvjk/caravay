"""Transcribe local Source Armenian audio through the managed backend."""

import importlib
import json
import os
import re
import subprocess
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol, TextIO, cast

from caraway.models import inspect
from caraway.settings import Backend, Settings
from caraway.translation import Format, Outcome, ValidationError

Stage = Literal["speech_to_text"]
RATE: Final = 16_000
SPAN: Final = RATE * 10


@dataclass(frozen=True)
class Issue:
    """Describe one machine-readable speech recognition issue."""

    stage: Stage
    code: str
    message: str


@dataclass(frozen=True)
class Result:
    """Hold one transcribed segment and its observable outcome."""

    outcome: Outcome
    text: str
    issues: tuple[Issue, ...]


class Runtime(Protocol):
    """Describe the lazily imported heavyweight speech backend module."""

    def validate(self, verbose: bool) -> bool:
        """Require the configured runtime device."""
        ...

    def load_speech(self, path: Path) -> object:
        """Load the pinned speech model once."""
        ...

    def transcribe(self, backend: object, source: str, audio: array[float]) -> Result:
        """Transcribe one audio segment."""
        ...


def runtime() -> Runtime:
    """Load the heavyweight backend only after local validation."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return cast(Runtime, importlib.import_module("caraway.runtime"))


def read(value: str) -> Path:
    """Require one readable local regular audio file."""
    if value == "-" or "://" in value:
        raise ValidationError("invalid_input: audio must be a local regular file")
    path = Path(value)
    try:
        with path.open("rb"):
            pass
    except OSError as error:
        raise ValidationError(
            f"invalid_input: {path} is not a readable regular file"
        ) from error
    if not path.is_file():
        raise ValidationError(f"invalid_input: {path} is not a readable regular file")
    return path


def capability(backend: str, source: str) -> Backend:
    """Validate the backend's Source Armenian speech capability."""
    if backend != Settings.backend_name or source != "hye":
        raise ValidationError(
            f"unsupported_capability: {backend} cannot transcribe {source}"
        )
    return cast(Backend, backend)


def validate(root: Path, verbose: bool) -> Path:
    """Require a ready snapshot and an available MPS runtime in order."""
    state = inspect(root)
    if state == "missing":
        raise ValidationError(
            "model_not_installed: run caraway models download before transcription"
        )
    if state == "invalid":
        raise ValidationError(
            "model_cache_invalid: installed model snapshot is invalid"
        )
    runtime().validate(verbose)
    return root / Settings.backend_name / Settings.revision


def decode(path: Path) -> tuple[array[float], ...]:
    """Decode mono 16 kHz audio into approximately ten-second segments."""
    command = (
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-ac",
        "1",
        "-ar",
        str(RATE),
        "-f",
        "f32le",
        "pipe:1",
    )
    try:
        process = subprocess.run(command, check=True, capture_output=True, timeout=3600)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValidationError(
            f"invalid_input: audio decoding failed for {path}"
        ) from error
    samples = array("f")
    samples.frombytes(process.stdout)
    return tuple(
        samples[index : index + SPAN] for index in range(0, len(samples), SPAN)
    )


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
            return text[: matches[len(words) - size * repeats].start()].rstrip()
    return text


def resolve(generated: str) -> Result:
    """Map generated speech text and repetition damage to an outcome."""
    text = trim(generated.strip())
    if text != generated.strip():
        problem = Issue(
            "speech_to_text", "repetition", "repeating transcript suffix was removed"
        )
        return Result("degraded" if text else "skipped", text, (problem,))
    if not text:
        problem = Issue(
            "speech_to_text", "empty_output", "transcription produced no useful text"
        )
        return Result("skipped", "", (problem,))
    return Result("completed", text, ())


def aggregate(results: tuple[Result, ...]) -> Outcome:
    """Combine attempted segment outcomes into one command outcome."""
    if any(result.outcome == "failed" for result in results):
        return "failed"
    useful = any(result.text for result in results)
    if useful and all(result.outcome == "completed" for result in results):
        return "completed"
    return "degraded" if useful else "skipped"


def dump(document: dict[str, object]) -> str:
    """Serialize one compact schema-version-one JSONL document."""
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"


def write(
    stream: TextIO,
    result: Result,
    index: int,
    representation: Format,
) -> bool:
    """Write and flush one completed transcription segment."""
    if representation == "text":
        if result.text:
            stream.write(f"{result.text.strip()}\n")
        stream.flush()
        return True
    stream.write(
        dump(
            {
                "schema_version": 1,
                "type": "segment",
                "index": index,
                "outcome": result.outcome,
                "text": result.text or None,
                "issues": [
                    {
                        "stage": problem.stage,
                        "code": problem.code,
                        "message": problem.message,
                    }
                    for problem in result.issues
                ],
            }
        )
    )
    stream.flush()
    return True


def finish(
    stream: TextIO,
    results: tuple[Result, ...],
    representation: Format,
    source: str,
    backend: Backend,
) -> bool:
    """Write and flush the terminal transcription summary."""
    if representation == "text":
        return True
    outcome = aggregate(results)
    counts = {
        name: sum(result.outcome == name for result in results)
        for name in ("completed", "degraded", "skipped", "failed")
    }
    summary: dict[str, object] = {
        "schema_version": 1,
        "type": "summary",
        "command": "transcribe",
        "outcome": outcome,
        "source_language": source,
        "backends": {"speech_to_text": backend},
        "segments": {"total": len(results), **counts},
    }
    if outcome == "failed":
        summary["error"] = next(
            {
                "stage": problem.stage,
                "code": problem.code,
                "message": problem.message,
            }
            for result in results
            if result.outcome == "failed"
            for problem in result.issues
        )
    stream.write(dump(summary))
    stream.flush()
    return True


def emit(
    stream: TextIO,
    results: tuple[Result, ...],
    representation: Format,
    source: str,
    backend: Backend,
) -> bool:
    """Write ordered transcription results and an orderly summary."""
    for index, result in enumerate(results):
        write(stream, result, index, representation)
    finish(stream, results, representation, source, backend)
    return True


def fail(
    stream: TextIO,
    representation: Format,
    source: str,
    backend: Backend,
    problem: Issue,
) -> bool:
    """Write a failed zero-segment summary after model loading fails."""
    if representation == "jsonl":
        document = {
            "schema_version": 1,
            "type": "summary",
            "command": "transcribe",
            "outcome": "failed",
            "source_language": source,
            "backends": {"speech_to_text": backend},
            "segments": {
                "total": 0,
                "completed": 0,
                "degraded": 0,
                "skipped": 0,
                "failed": 0,
            },
            "error": {
                "stage": problem.stage,
                "code": problem.code,
                "message": problem.message,
            },
        }
        stream.write(dump(document))
        stream.flush()
    return True


def load(path: Path) -> object:
    """Load the pinned speech model once for a transcription command."""
    return runtime().load_speech(path)


def transcribe(backend: object, source: str, audio: array[float]) -> Result:
    """Transcribe one audio segment offline on MPS with FP16."""
    return runtime().transcribe(backend, source, audio)
